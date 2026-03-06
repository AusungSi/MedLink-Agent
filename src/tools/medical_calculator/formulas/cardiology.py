# filename: formulas/cardiology.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def calculate_grace_score(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算GRACE缺血风险评分。用于评估急性冠脉综合征(ACS)患者的院内死亡风险。
    """
    score = 0
    
    # 1. 年龄 (岁)
    age = params['age']
    if 30 <= age <= 39: score += 8
    elif 40 <= age <= 49: score += 25
    elif 50 <= age <= 59: score += 41
    elif 60 <= age <= 69: score += 58
    elif 70 <= age <= 79: score += 75
    elif age >= 80: score += 91

    # 2. 心率 (次/分)
    heart_rate = params['heart_rate']
    if 70 <= heart_rate <= 89: score += 3
    elif 90 <= heart_rate <= 109: score += 9
    elif 110 <= heart_rate <= 149: score += 15
    elif 150 <= heart_rate <= 199: score += 24
    elif heart_rate >= 200: score += 38

    # 3. 收缩压 (mmHg)
    sbp = params['systolic_bp']
    if sbp < 80: score += 58
    elif 80 <= sbp <= 99: score += 53
    elif 100 <= sbp <= 119: score += 43
    elif 120 <= sbp <= 139: score += 34
    elif 140 <= sbp <= 159: score += 24
    elif 160 <= sbp <= 199: score += 10

    # 4. 血肌酐 (mg/dL) - 注意单位转换
    creatinine_mg_dl = params['creatinine_mg_dl']
    if 0.4 <= creatinine_mg_dl <= 0.79: score += 4
    elif 0.8 <= creatinine_mg_dl <= 1.19: score += 7
    elif 1.2 <= creatinine_mg_dl <= 1.59: score += 10
    elif 1.6 <= creatinine_mg_dl <= 1.99: score += 13
    elif 2.0 <= creatinine_mg_dl <= 3.99: score += 21
    elif creatinine_mg_dl >= 4.0: score += 28
    
    # 5. Killip分级 (I-IV)
    killip_class = params['killip_class']
    if killip_class == 2: score += 20
    elif killip_class == 3: score += 39
    elif killip_class == 4: score += 59
    
    # 6. 入院时心脏骤停
    if params.get('cardiac_arrest_at_admission', False):
        score += 39
        
    # 7. ST段改变
    if params.get('st_segment_deviation', False):
        score += 28
        
    # 8. 心肌标志物升高
    if params.get('elevated_cardiac_markers', False):
        score += 14

    # 根据总分评估院内死亡风险
    if score <= 108:
        risk_level = "低危 (<1% 院内死亡风险)"
        recommendation = "患者院内死亡风险低。根据指南，可考虑早期非侵入性风险评估，若无禁忌症和复发性缺血，可在24-48小时内出院。"
    elif 109 <= score <= 140:
        risk_level = "中危 (1-3% 院内死亡风险)"
        recommendation = "患者院内死亡风险中等。建议住院观察，并考虑早期（<72小时）的侵入性策略（冠状动脉造影）。"
    else: # score > 140
        risk_level = "高危 (>3% 院内死亡风险)"
        recommendation = "患者院内死亡风险高。强烈建议采取紧急（<2小时）或早期（<24小时）的侵入性策略（冠状动脉造影和血运重建）。"

    return ClinicalScoreResult(
        score_name="GRACE 缺血风险评分",
        score_value=score,
        risk_level=risk_level,
        recommendation=recommendation
    )