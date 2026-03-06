# filename: formulas/renal.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def _get_ckd_stage_recommendation(egfr: float) -> (str, str):
    """根据eGFR值返回CKD分期和建议"""
    if egfr >= 90:
        stage = "CKD 1期 (或正常)"
        recommendation = "肾功能正常或轻度下降，但可能存在肾损伤的其他证据（如蛋白尿）。建议定期监测。"
    elif 60 <= egfr < 90:
        stage = "CKD 2期"
        recommendation = "肾功能轻度下降。建议控制血压、血糖等危险因素，定期复查肾功能。"
    elif 30 <= egfr < 60:
        stage = "CKD 3期"
        recommendation = "肾功能中度下降。需要评估并治疗并发症，如贫血、骨病等。"
    elif 15 <= egfr < 30:
        stage = "CKD 4期"
        recommendation = "肾功能重度下降。应为肾脏替代治疗（透析或移植）做准备。"
    else:  # egfr < 15
        stage = "CKD 5期 (肾衰竭)"
        recommendation = "肾功能极重度下降或已进入终末期肾病。需要开始肾脏替代治疗。"
    return stage, recommendation

def calculate_cockcroft_gault(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算肌酐清除率 (Cockcroft-Gault 公式)。需要: age(年龄), weight_kg(体重kg), creatinine_mg_dl(血肌酐mg/dL), gender('male'或'female')。
    """
    age = params['age']
    weight = params['weight_kg']
    creatinine = params['creatinine_mg_dl']
    gender = params['gender']

    if creatinine <= 0:
        raise ValueError("血肌酐必须是正数。")

    crcl = ((140 - age) * weight) / (72 * creatinine)
    if gender == 'female':
        crcl *= 0.85
        
    crcl_rounded = round(crcl, 2)

    return ClinicalScoreResult(
        score_name="肌酐清除率 (Cockcroft-Gault)",
        score_value=crcl_rounded,
        risk_level=f"{crcl_rounded} mL/min",
        recommendation="经典公式，用于评估肾功能和许多药物的剂量调整。注意该公式未对体表面积进行标准化。"
    )

def calculate_egfr_mdrd(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算eGFR (2006年改良的IMDS-MDRD公式)。需要: age(年龄), creatinine_mg_dl(血肌酐mg/dL), gender('male'或'female'), race('black'或'non-black')。
    """
    age = params['age']
    creatinine = params['creatinine_mg_dl']
    gender = params['gender']
    race = params['race']

    if creatinine <= 0:
        raise ValueError("血肌酐必须是正数。")

    # MDRD公式: eGFR = 175 * (Creatinine)^-1.154 * (Age)^-0.203 * (0.742 if female) * (1.212 if black)
    egfr = 175 * (creatinine ** -1.154) * (age ** -0.203)
    
    if gender == 'female':
        egfr *= 0.742
    if race == 'black':
        egfr *= 1.212

    egfr_rounded = round(egfr, 2)
    stage, recommendation = _get_ckd_stage_recommendation(egfr_rounded)

    return ClinicalScoreResult(
        score_name="eGFR (IMDS-MDRD 2006)",
        score_value=egfr_rounded,
        risk_level=f"{stage}: {egfr_rounded} mL/min/1.73m²",
        recommendation=recommendation
    )

def calculate_egfr_ckd_epi(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算eGFR (CKD-EPI 2009 肌酐公式)。需要: age(年龄), creatinine_mg_dl(血肌酐mg/dL), gender('male'或'female'), race('black'或'non-black')。
    """
    age = params['age']
    scr = params['creatinine_mg_dl']
    gender = params['gender']
    race = params['race']

    if scr <= 0:
        raise ValueError("血肌酐必须是正数。")

    kappa = 0.7 if gender == 'female' else 0.9
    alpha = -0.329 if gender == 'female' else -0.411
    
    gender_factor = 1.018 if gender == 'female' else 1.0
    race_factor = 1.159 if race == 'black' else 1.0
    
    # CKD-EPI公式核心
    egfr = 141 * (min(scr / kappa, 1) ** alpha) * (max(scr / kappa, 1) ** -1.209) * (0.993 ** age) * gender_factor * race_factor
        
    egfr_rounded = round(egfr, 2)
    stage, recommendation = _get_ckd_stage_recommendation(egfr_rounded)

    return ClinicalScoreResult(
        score_name="eGFR (CKD-EPI 2009)",
        score_value=egfr_rounded,
        risk_level=f"{stage}: {egfr_rounded} mL/min/1.73m²",
        recommendation=f"CKD-EPI公式在eGFR > 60时比MDRD更准确。{recommendation}"
    )

def calculate_pediatric_egfr_schwartz(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算儿童估算肾小球滤过率(eGFR)，采用2009年更新的“床边”Schwartz公式。需要: height_cm(身高cm), creatinine_mg_dl(血肌酐mg/dL)。
    """
    height = params['height_cm']
    creatinine = params['creatinine_mg_dl']

    if height <= 0 or creatinine <= 0:
        raise ValueError("身高和血肌酐必须是正数。")

    # 2009 IDMS-traceable "Bedside Schwartz" 公式使用统一的 k = 0.413
    k = 0.413
    
    # Schwartz公式: eGFR = (k * 身高cm) / 血肌酐mg/dL
    egfr = (k * height) / creatinine
    egfr_rounded = round(egfr, 2)
    
    stage, recommendation = _get_ckd_stage_recommendation(egfr_rounded)

    return ClinicalScoreResult(
        score_name="儿童 eGFR (Bedside Schwartz)",
        score_value=egfr_rounded,
        risk_level=f"{stage}: {egfr_rounded} mL/min/1.73m²",
        recommendation=f"专用于评估1-18岁儿童及青少年肾功能。{recommendation}"
    )