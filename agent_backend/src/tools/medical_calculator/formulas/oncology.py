# filename: formulas/oncology.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def calculate_carboplatin_dose(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算卡铂剂量 (Calvert公式)。需要: target_auc(目标AUC值), gfr(肾小球滤过率mL/min)。
    """
    target_auc = params['target_auc']
    gfr = params['gfr'] # gfr可以直接传入，或通过调用其他eGFR公式计算得到

    # Calvert 公式: 总剂量(mg) = 目标AUC * (GFR + 25)
    dose_mg = target_auc * (gfr + 25)
    dose_rounded = round(dose_mg, 2)
    
    recommendation = (
        f"为达到目标AUC {target_auc} mg/mL·min, 建议卡铂总剂量为 {dose_rounded} mg。 "
        "实际剂量需由临床医生根据患者具体情况（如前期化疗史、骨髓状况）进行调整。 "
        "目标AUC常规范围为4-7。"
    )

    return ClinicalScoreResult(
        score_name="卡铂剂量 (Calvert)",
        score_value=dose_rounded,
        risk_level=f"总剂量: {dose_rounded} mg",
        recommendation=recommendation
    )

def calculate_charlson_cci(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算查尔森合并症指数 (CCI)。需要一个包含多个疾病状况(布尔值)的字典。
    """
    score = 0
    
    # 权重为 1 的疾病
    score += 1 if params.get('myocardial_infarction', False) else 0
    score += 1 if params.get('congestive_heart_failure', False) else 0
    score += 1 if params.get('peripheral_vascular_disease', False) else 0
    score += 1 if params.get('cerebrovascular_disease', False) else 0
    score += 1 if params.get('dementia', False) else 0
    score += 1 if params.get('copd', False) else 0
    score += 1 if params.get('connective_tissue_disease', False) else 0
    score += 1 if params.get('ulcer_disease', False) else 0
    score += 1 if params.get('mild_liver_disease', False) else 0
    # 糖尿病：无并发症得1分，有终末器官损害得2分，不叠加
    if params.get('diabetes_with_end_organ_damage', False):
        score += 2
    elif params.get('diabetes_uncomplicated', False):
        score += 1

    # 权重为 2 的疾病
    score += 2 if params.get('hemiplegia_or_paraplegia', False) else 0
    score += 2 if params.get('moderate_to_severe_renal_disease', False) else 0
    
    # 权重为 3 的疾病
    score += 3 if params.get('moderate_to_severe_liver_disease', False) else 0

    # 权重为 6 的疾病
    score += 6 if params.get('metastatic_solid_tumor', False) else 0
    # 实体瘤/白血病/淋巴瘤：转移性实体瘤得6分，否则得2分，不叠加
    if not params.get('metastatic_solid_tumor', False):
        score += 2 if params.get('any_malignancy', False) else 0 # 包括白血病、淋巴瘤
    score += 6 if params.get('aids', False) else 0
    
    # 根据年龄调整
    age = params.get('age', 0)
    if 50 <= age <= 59:
        score += 1
    elif 60 <= age <= 69:
        score += 2
    elif 70 <= age <= 79:
        score += 3
    elif age >= 80:
        score += 4

    # 评估10年生存率
    ten_year_survival_prob = 0.983 ** (math.exp(score * 0.9))
    ten_year_survival_percent = round(ten_year_survival_prob * 100, 1)

    if score == 0:
        risk_level = "低风险"
        recommendation = f"CCI评分为0，合并症负担低。预计10年生存率约为 {ten_year_survival_percent}%。"
    elif 1 <= score <= 2:
        risk_level = "中等风险"
        recommendation = f"CCI评分为{score}，存在中等合并症负担。预计10年生存率约为 {ten_year_survival_percent}%。"
    else: # score >= 3
        risk_level = "高风险"
        recommendation = f"CCI评分为{score}，合并症负担高，显著影响长期预后。预计10年生存率约为 {ten_year_survival_percent}%。"

    return ClinicalScoreResult(
        score_name="年龄校正查尔森合并症指数 (CCI)",
        score_value=score,
        risk_level=risk_level,
        recommendation=recommendation
    )