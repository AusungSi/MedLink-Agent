# filename: formulas/endocrinology.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any, Optional

def diagnose_diabetes_who(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    根据WHO 2019标准诊断糖尿病。需要至少一个血糖指标: fpg_mmol_l, ogtt_2h_mmol_l, hba1c_percent, 或 random_pg_mmol_l (需伴有症状)。
    """
    fpg: Optional[float] = params.get('fpg_mmol_l')
    ogtt_2h: Optional[float] = params.get('ogtt_2h_mmol_l')
    hba1c: Optional[float] = params.get('hba1c_percent')
    random_pg: Optional[float] = params.get('random_pg_mmol_l')
    has_symptoms: bool = params.get('has_symptoms', False)

    diagnosis = "信息不足"
    recommendation = "请输入至少一项血糖检测结果以进行评估。"
    score_value = -1 # -1 for insufficient data

    # 检查糖尿病标准
    if (fpg is not None and fpg >= 7.0) or \
       (ogtt_2h is not None and ogtt_2h >= 11.1) or \
       (hba1c is not None and hba1c >= 6.5) or \
       (random_pg is not None and random_pg >= 11.1 and has_symptoms):
        diagnosis = "糖尿病 (Diabetes Mellitus)"
        recommendation = "检测结果符合糖尿病诊断标准。任何一项阳性结果都应在另一天重复检测进行确认（除非存在明确的高血糖危象）。请立即咨询医生进行确诊和治疗。"
        score_value = 2
    # 检查糖尿病前期标准 (如果未诊断为糖尿病)
    elif (fpg is not None and 6.1 <= fpg <= 6.9) or \
         (ogtt_2h is not None and 7.8 <= ogtt_2h <= 11.0) or \
         (hba1c is not None and 5.7 <= hba1c <= 6.4):
        diagnosis = "糖尿病前期 (Prediabetes)"
        recommendation = "检测结果提示为糖尿病前期，这是发展为2型糖尿病的高风险状态。建议进行生活方式干预（饮食、运动），并定期监测血糖。"
        score_value = 1
    # 检查是否正常 (如果至少有一项输入且不满足以上条件)
    elif fpg is not None or ogtt_2h is not None or hba1c is not None or random_pg is not None:
        diagnosis = "血糖正常 (Normal Glucose Tolerance)"
        recommendation = "根据所提供的数据，您的血糖水平在正常范围内。请继续保持健康的生活方式。"
        score_value = 0

    return ClinicalScoreResult(
        score_name="糖尿病诊断标准 (WHO)",
        score_value=score_value,
        risk_level=diagnosis,
        recommendation=recommendation
    )