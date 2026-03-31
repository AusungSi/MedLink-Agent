# backend/app/api/doctor_api.py
import re
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services import doctor_service
from ..schemas.doctor_schema import DoctorListSchema
from ..models.user_model import UserModel
from ..models.consultation_model import AIConsultationModel, ChatMessageModel
from ..models.medical_record_model import MedicalRecordModel
from ..core.extensions import db
import logging

# [cite: 1602]
doctor_bp = Blueprint('doctor_api', __name__, url_prefix='/api/doctors')
doctor_patient_bp = Blueprint('doctor_patient_api', __name__, url_prefix='/api/doctor')

_SCREENING_PREFIX = '已提交【甲状腺筛查】信息'


def _safe_text(value):
    return (value or '').strip()


def _split_image_paths(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [chunk.strip() for chunk in str(value).split(',') if chunk.strip()]


def _extract_urls(text):
    if not text:
        return []
    return re.findall(r'https?://[^\s]+', text)


def _calculate_age(birth_date):
    if not birth_date:
        return None
    today = datetime.utcnow().date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _normalize_file_url(path):
    path = _safe_text(path)
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://'):
        return path
    if not path.startswith('/'):
        path = '/' + path
    return path


def _extract_screening_payload_from_message(content):
    payload = {
        'age': None,
        'sex': '',
        'tsh': None,
        'neck_radiation_exposure': None,
        'family_thyroid_cancer_history': None,
        'characteristics': {
            'composition': '',
            'echogenicity': '',
            'shape': '',
            'margin': '',
            'echogenic_foci': ''
        },
        'report_text': ''
    }

    text = _safe_text(content)
    if not text.startswith(_SCREENING_PREFIX):
        return payload

    age_match = re.search(r'基本信息：\s*(\d+)\s*岁', text)
    if age_match:
        payload['age'] = int(age_match.group(1))

    sex_match = re.search(r'性别\s*([FMU男女未知其他/]+)', text)
    if sex_match:
        payload['sex'] = sex_match.group(1)

    tsh_match = re.search(r'TSH：\s*([\d.]+)', text)
    if tsh_match:
        try:
            payload['tsh'] = float(tsh_match.group(1))
        except ValueError:
            payload['tsh'] = None

    radiation_match = re.search(r'颈部放射线暴露史：\s*(有|无|不确定)', text)
    if radiation_match:
        payload['neck_radiation_exposure'] = radiation_match.group(1) == '有'

    family_match = re.search(r'家族甲状腺癌病史：\s*(有|无|不确定)', text)
    if family_match:
        payload['family_thyroid_cancer_history'] = family_match.group(1) == '有'

    ultrasound_match = re.search(r'超声特征：(.+)', text)
    if ultrasound_match:
        seg = ultrasound_match.group(1)
        pairs = {
            'composition': r'成分=([^、\n]+)',
            'echogenicity': r'回声=([^、\n]+)',
            'shape': r'形状=([^、\n]+)',
            'margin': r'边缘=([^、\n]+)',
            'echogenic_foci': r'局灶性强回声=([^、\n]+)'
        }
        for field, pattern in pairs.items():
            m = re.search(pattern, seg)
            if m:
                payload['characteristics'][field] = m.group(1).strip()

    report_match = re.search(r'报告描述：(.+)', text)
    if report_match:
        payload['report_text'] = report_match.group(1).strip()

    return payload


def _extract_screening_from_structured_symptoms(structured_symptoms):
    if not isinstance(structured_symptoms, dict):
        return None

    screening = structured_symptoms.get('thyroid_screening')
    if isinstance(screening, dict):
        payload = screening.get('payload') if isinstance(screening.get('payload'), dict) else {}
        file_urls = screening.get('file_urls') if isinstance(screening.get('file_urls'), list) else []
        return {
            'payload': payload,
            'file_urls': [str(u).strip() for u in file_urls if str(u).strip()]
        }

    if 'characteristics' in structured_symptoms:
        return {
            'payload': structured_symptoms,
            'file_urls': [str(u).strip() for u in (structured_symptoms.get('file_urls') or []) if str(u).strip()]
        }

    return None


def _get_latest_patient_screening_from_consultations(patient_id):
    consultations = AIConsultationModel.query.filter_by(patient_id=patient_id).order_by(AIConsultationModel.created_at.desc()).all()
    for c in consultations:
        item = _extract_screening_from_structured_symptoms(c.structured_symptoms)
        if item and isinstance(item.get('payload'), dict):
            return item
    return None


def _build_patient_screening_response(user, screening_item=None, screening_message=None, report_record=None):
    if screening_item and isinstance(screening_item.get('payload'), dict):
        screening_payload = screening_item.get('payload')
        image_urls = [str(u).strip() for u in (screening_item.get('file_urls') or []) if str(u).strip()]
    else:
        screening_payload = _extract_screening_payload_from_message(screening_message.content if screening_message else '')
        image_urls = _extract_urls(screening_message.content if screening_message else '')

    report_text = screening_payload.get('report_text') or ''

    if report_record:
        if not report_text:
            report_text = _safe_text(report_record.history_present_illness) or _safe_text(report_record.chief_complaint)
        image_urls.extend([_normalize_file_url(p) for p in _split_image_paths(report_record.image_paths)])

    # 去重并保持顺序
    seen = set()
    dedup_urls = []
    for url in image_urls:
        if url and url not in seen:
            seen.add(url)
            dedup_urls.append(url)

    age = screening_payload.get('age')
    if age is None:
        age = _calculate_age(user.birth_date)

    sex = screening_payload.get('sex') or _safe_text(user.gender) or '未知'

    characteristics = screening_payload.get('characteristics') or {}
    return {
        'id': user.id,
        'name': _safe_text(user.full_name) or f'患者{user.id}',
        'sex': sex,
        'age': age if age is not None else 0,
        'reportText': report_text,
        'imageUrls': dedup_urls,
        'screening': {
            'age': age,
            'sex': sex,
            'tsh': screening_payload.get('tsh'),
            'neck_radiation_exposure': screening_payload.get('neck_radiation_exposure'),
            'family_thyroid_cancer_history': screening_payload.get('family_thyroid_cancer_history'),
            'characteristics': {
                'composition': characteristics.get('composition') or '',
                'echogenicity': characteristics.get('echogenicity') or '',
                'shape': characteristics.get('shape') or '',
                'margin': characteristics.get('margin') or '',
                'echogenic_foci': characteristics.get('echogenic_foci') or ''
            },
            'report_text': report_text
        }
    }

@doctor_bp.route('', methods=['GET']) # [cite: 1601]
@jwt_required() # [cite: 1607-1609]
def get_doctor_list():
    """
    API #16: 获取医生列表
    
    """
    try:
        # 1. 获取科室筛选参数
        # [cite: 1606]
        # 我们假设前端传递的是 DepartmentModel 的整数ID
        department_id = request.args.get('departmentId', type=int)
        
        # 2. 调用服务层获取医生数据
        doctors = doctor_service.get_doctors(department_id)
        
        # 3. 序列化数据
        # [cite: 1612]
        schema = DoctorListSchema(many=True)
        result = schema.dump(doctors)
        
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Error in /api/doctors GET: {e}", exc_info=True)
        # [cite: 1630-1633]
        return jsonify({"error_code": 500, "message": "获取医生列表失败"}), 500


@doctor_patient_bp.route('/patients', methods=['GET'])
@jwt_required()
def get_doctor_patient_list():
    """医生工作站患者列表：优先返回提交过甲状腺筛查的患者。"""
    try:
        doctor_id = get_jwt_identity()
        doctor = UserModel.query.filter_by(id=doctor_id).first()
        if not doctor or doctor.role != 'doctor':
            return jsonify({"error_code": 403, "message": "仅医生可访问"}), 403

        # 统一真值来源：AIConsultationModel.structured_symptoms 中的 thyroid_screening
        consultations = AIConsultationModel.query.filter(AIConsultationModel.structured_symptoms.isnot(None)).order_by(AIConsultationModel.created_at.desc()).all()

        latest_screening_by_patient = {}
        for c in consultations:
            if c.patient_id in latest_screening_by_patient:
                continue
            screening_item = _extract_screening_from_structured_symptoms(c.structured_symptoms)
            if screening_item and isinstance(screening_item.get('payload'), dict):
                latest_screening_by_patient[c.patient_id] = {
                    'item': screening_item,
                    'consultation_id': c.id
                }

        patient_ids = list(latest_screening_by_patient.keys())
        if not patient_ids:
            return jsonify([]), 200

        users = UserModel.query.filter(UserModel.id.in_(patient_ids)).all()
        user_map = {u.id: u for u in users}

        result = []
        for patient_id in patient_ids:
            user = user_map.get(patient_id)
            if not user:
                continue

            screening_item = latest_screening_by_patient.get(patient_id, {}).get('item')

            latest_msg = db.session.query(ChatMessageModel).join(
                AIConsultationModel,
                AIConsultationModel.id == ChatMessageModel.consultation_id
            ).filter(
                AIConsultationModel.patient_id == patient_id,
                ChatMessageModel.sender_type == 'user',
                ChatMessageModel.content.like(f'{_SCREENING_PREFIX}%')
            ).order_by(ChatMessageModel.id.desc()).first()

            latest_record = MedicalRecordModel.query.filter_by(patient_id=patient_id).order_by(MedicalRecordModel.created_at.desc()).first()
            result.append(_build_patient_screening_response(user, screening_item, latest_msg, latest_record))

        result.sort(key=lambda item: item.get('id') or 0, reverse=True)
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Error in /api/doctor/patients GET: {e}", exc_info=True)
        return jsonify({"error_code": 500, "message": "获取患者列表失败"}), 500


@doctor_patient_bp.route('/patients/<int:patient_id>/report', methods=['GET'])
@jwt_required()
def get_doctor_patient_report(patient_id):
    """医生工作站患者详情：返回与甲状腺筛查表单一致的字段和附件。"""
    try:
        doctor_id = get_jwt_identity()
        doctor = UserModel.query.filter_by(id=doctor_id).first()
        if not doctor or doctor.role != 'doctor':
            return jsonify({"error_code": 403, "message": "仅医生可访问"}), 403

        user = UserModel.query.filter_by(id=patient_id, role='patient').first()
        if not user:
            return jsonify({"error_code": 404, "message": "未找到患者"}), 404

        latest_msg = db.session.query(ChatMessageModel).join(
            AIConsultationModel,
            AIConsultationModel.id == ChatMessageModel.consultation_id
        ).filter(
            AIConsultationModel.patient_id == patient_id,
            ChatMessageModel.sender_type == 'user',
            ChatMessageModel.content.like(f'{_SCREENING_PREFIX}%')
        ).order_by(ChatMessageModel.timestamp.desc(), ChatMessageModel.id.desc()).first()

        # 使用“最近一条包含结构化筛查信息”的会话，避免最新会话无筛查时数据丢失
        screening_item = _get_latest_patient_screening_from_consultations(patient_id)

        latest_record = MedicalRecordModel.query.filter_by(patient_id=patient_id).order_by(MedicalRecordModel.created_at.desc()).first()

        if not screening_item and not latest_msg and not latest_record:
            return jsonify({"error_code": 404, "message": "该患者暂无甲状腺筛查或病历报告"}), 404

        return jsonify(_build_patient_screening_response(user, screening_item, latest_msg, latest_record)), 200
    except Exception as e:
        logging.error(f"Error in /api/doctor/patients/<id>/report GET: {e}", exc_info=True)
        return jsonify({"error_code": 500, "message": "获取患者报告失败"}), 500