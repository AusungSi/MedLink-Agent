# filename: formulas/body_composition.py

import math
from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def calculate_body_fat_bmi(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    根据BMI估算体脂率。需要: bmi(体重指数), age(年龄), gender('male'或'female')。
    """
    bmi = params['bmi']
    age = params['age']
    gender = params['gender']
    
    gender_code = 1 if gender == 'male' else 0
    
    # Deurenberg 公式
    body_fat_percentage = (1.20 * bmi) + (0.23 * age) - (10.8 * gender_code) - 5.4
    bfp_rounded = round(body_fat_percentage, 2)
    
    # 简单的风险分类
    risk_level = "正常范围"
    if (gender == 'female' and bfp_rounded > 32) or (gender == 'male' and bfp_rounded > 25):
        risk_level = "肥胖"
    elif (gender == 'female' and 25 < bfp_rounded <= 32) or (gender == 'male' and 18 < bfp_rounded <= 25):
        risk_level = "超重"
    elif (gender == 'female' and bfp_rounded < 18) or (gender == 'male' and bfp_rounded < 8):
        risk_level = "偏瘦"
        
    return ClinicalScoreResult(
        score_name="体脂率 (根据BMI估算)",
        score_value=bfp_rounded,
        risk_level=f"{risk_level}: {bfp_rounded}%",
        recommendation="这是一个基于人群数据的估算值，个体差异较大。如需精确测量，建议使用皮褶厚度法、生物电阻抗分析(BIA)或DEXA扫描。"
    )

def calculate_body_fat_waist(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    根据腰围估算体脂率 (美国海军方法)。需要: height_cm(身高), neck_cm(颈围), waist_cm(腰围), gender('male'或'female'), 以及女性需要的hip_cm(臀围)。
    """
    height = params['height_cm']
    neck = params['neck_cm']
    waist = params['waist_cm']
    gender = params['gender']

    bfp = 0
    if gender == 'male':
        # BFP% = 495 / (1.0324 - 0.19077 * log10(waist - neck) + 0.15456 * log10(height)) - 450
        try:
            bfp = 495 / (1.0324 - 0.19077 * math.log10(waist - neck) + 0.15456 * math.log10(height)) - 450
        except ValueError:
            raise ValueError("腰围必须大于颈围。请检查输入值。")
    elif gender == 'female':
        hip = params['hip_cm']
        # BFP% = 495 / (1.29579 - 0.35004 * log10(waist + hip - neck) + 0.22100 * log10(height)) - 450
        try:
            bfp = 495 / (1.29579 - 0.35004 * math.log10(waist + hip - neck) + 0.22100 * math.log10(height)) - 450
        except ValueError:
            raise ValueError("（腰围+臀围）必须大于颈围。请检查输入值。")
    else:
        raise ValueError("性别必须是 'male' 或 'female'。")
        
    bfp_rounded = round(bfp, 2)
    
    # 使用与BMI法相同的风险分类
    risk_level = "正常范围"
    if (gender == 'female' and bfp_rounded > 32) or (gender == 'male' and bfp_rounded > 25):
        risk_level = "肥胖"
    elif (gender == 'female' and 25 < bfp_rounded <= 32) or (gender == 'male' and 18 < bfp_rounded <= 25):
        risk_level = "超重"
    elif (gender == 'female' and bfp_rounded < 18) or (gender == 'male' and bfp_rounded < 8):
        risk_level = "偏瘦"

    return ClinicalScoreResult(
        score_name="体脂率 (根据围度估算)",
        score_value=bfp_rounded,
        risk_level=f"{risk_level}: {bfp_rounded}%",
        recommendation="此方法通常比基于BMI的估算更准确，因为它考虑了身体脂肪的分布。但仍是一种估算方法。"
    )