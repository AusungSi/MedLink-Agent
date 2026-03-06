# filename: formulas/general.py

import math
from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def calculate_bmi(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算体重指数 (BMI)。需要: height_cm(身高cm), weight_kg(体重kg)。
    """
    height_m = params['height_cm'] / 100
    weight = params['weight_kg']
    
    if height_m <= 0 or weight <= 0:
        raise ValueError("身高和体重必须是正数。")

    bmi = weight / (height_m ** 2)
    bmi_rounded = round(bmi, 2)

    # 根据中国成人标准进行分类
    if bmi < 18.5:
        risk_level = "体重过轻"
        recommendation = "可能存在营养不良风险。建议咨询医生或营养师，增加营养摄入，保持均衡饮食和适度运动。"
    elif 18.5 <= bmi < 24:
        risk_level = "正常范围"
        recommendation = "体重在健康范围，请继续保持健康的生活方式。"
    elif 24 <= bmi < 28:
        risk_level = "超重"
        recommendation = "患相关疾病的风险增加。建议调整饮食结构，增加体育锻炼以控制体重。"
    else: # bmi >= 28
        risk_level = "肥胖"
        recommendation = "患慢性病风险显著增加。强烈建议寻求专业医疗指导，制定个性化的减重计划。"

    return ClinicalScoreResult(
        score_name="体重指数 (BMI)",
        score_value=bmi_rounded,
        risk_level=risk_level,
        recommendation=recommendation
    )


def calculate_bsa(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算体表面积 (BSA)，采用Mosteller公式。需要: height_cm(身高cm), weight_kg(体重kg)。
    """
    height = params['height_cm']
    weight = params['weight_kg']

    if height <= 0 or weight <= 0:
        raise ValueError("身高和体重必须是正数。")

    # Mosteller 公式: BSA (m²) = sqrt((身高cm * 体重kg) / 3600)
    bsa = math.sqrt((height * weight) / 3600)
    bsa_rounded = round(bsa, 2)

    return ClinicalScoreResult(
        score_name="体表面积 (BSA) - Mosteller",
        score_value=bsa_rounded,
        risk_level=f"{bsa_rounded} m²",
        recommendation="常用于计算化疗药物、强心剂等药物的精确剂量，以及评估肾功能和心脏功能指数。"
    )


def calculate_ibw(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算标准体重 (IBW)，采用Devine公式。需要: height_cm(身高cm), gender('male'或'female')。
    """
    height_cm = params['height_cm']
    gender = params['gender']
    
    # Devine公式基于身高超过5英尺（152.4cm）的部分计算
    inches_over_5_feet = (height_cm - 152.4) / 2.54
    
    if inches_over_5_feet < 0:
        recommendation = "Devine公式主要适用于身高超过152.4cm (5英尺)的个体。"
        ibw = 0
    else:
        if gender == 'male':
            # 男性: 50kg + 2.3kg * (超过5英尺的英寸数)
            ibw = 50 + (2.3 * inches_over_5_feet)
        elif gender == 'female':
            # 女性: 45.5kg + 2.3kg * (超过5英尺的英寸数)
            ibw = 45.5 + (2.3 * inches_over_5_feet)
        else:
            raise ValueError("性别必须是 'male' 或 'female'。")
        recommendation = "用于评估营养状况和计算某些药物剂量（如呼吸机参数）。"

    ibw_rounded = round(ibw, 2)

    return ClinicalScoreResult(
        score_name="标准体重 (IBW) - Devine",
        score_value=ibw_rounded,
        risk_level=f"{ibw_rounded} kg",
        recommendation=recommendation
    )