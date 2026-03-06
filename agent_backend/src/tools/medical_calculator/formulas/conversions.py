# filename: formulas/conversions.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def convert_steroid_dose(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    进行常用糖皮质激素的等效抗炎剂量换算。需要: from_steroid(源激素名), to_steroid(目标激素名), dose(源激素剂量)。
    """
    # 等效抗炎剂量 (以5mg泼尼松为基准)
    equivalents = {
        'hydrocortisone': 20,
        'prednisone': 5,
        'prednisolone': 5,
        'methylprednisolone': 4,
        'triamcinolone': 4,
        'dexamethasone': 0.75,
        'betamethasone': 0.6
    }
    
    from_steroid = params['from_steroid'].lower()
    to_steroid = params['to_steroid'].lower()
    dose = params['dose']
    
    if from_steroid not in equivalents or to_steroid not in equivalents:
        raise ValueError(f"不支持的激素类型。支持的类型: {', '.join(equivalents.keys())}")

    # 转换为“泼尼松单位”
    prednisone_units = dose / equivalents[from_steroid]
    # 从“泼尼松单位”转换为目标激素剂量
    converted_dose = prednisone_units * equivalents[to_steroid]
    
    converted_dose_rounded = round(converted_dose, 2)
    
    return ClinicalScoreResult(
        score_name="激素剂量换算",
        score_value=converted_dose_rounded,
        risk_level=f"{dose} mg {from_steroid.capitalize()} ≈ {converted_dose_rounded} mg {to_steroid.capitalize()}",
        recommendation="此换算基于等效抗炎效应。不同激素的盐皮质激素活性、半衰期和副作用谱可能不同，临床应用时需综合考虑。"
    )

def convert_glucose_units(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    进行血糖单位换算 (mg/dL 和 mmol/L)。需要: value(数值), from_unit('mg_dl'或'mmol_l')。
    """
    value = params['value']
    from_unit = params['from_unit']
    CONVERSION_FACTOR = 18.0182
    
    if from_unit == 'mg_dl':
        to_unit = 'mmol/L'
        result = value / CONVERSION_FACTOR
    elif from_unit == 'mmol_l':
        to_unit = 'mg/dL'
        result = value * CONVERSION_FACTOR
    else:
        raise ValueError("单位必须是 'mg_dl' 或 'mmol_l'。")
        
    result_rounded = round(result, 2)
    
    return ClinicalScoreResult(
        score_name="血糖单位换算",
        score_value=result_rounded,
        risk_level=f"{value} {from_unit.replace('_', '/')} = {result_rounded} {to_unit}",
        recommendation="国际单位制(SI)使用mmol/L，美国常用mg/dL。"
    )

def convert_lipid_units(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    进行血脂单位换算。需要: lipid_type('cholesterol'或'triglyceride'), value(数值), from_unit('mg_dl'或'mmol_l')。
    """
    FACTORS = {
        'cholesterol': 38.67,  # for TC, HDL, LDL
        'triglyceride': 88.57
    }
    lipid_type = params['lipid_type'].lower()
    if lipid_type not in FACTORS:
        raise ValueError("血脂类型必须是 'cholesterol' 或 'triglyceride'。")
        
    value = params['value']
    from_unit = params['from_unit']
    conversion_factor = FACTORS[lipid_type]

    if from_unit == 'mg_dl':
        to_unit = 'mmol/L'
        result = value / conversion_factor
    elif from_unit == 'mmol_l':
        to_unit = 'mg/dL'
        result = value * conversion_factor
    else:
        raise ValueError("单位必须是 'mg_dl' 或 'mmol_l'。")
        
    result_rounded = round(result, 2)
    
    return ClinicalScoreResult(
        score_name=f"{lipid_type.capitalize()} 单位换算",
        score_value=result_rounded,
        risk_level=f"{value} {from_unit.replace('_', '/')} = {result_rounded} {to_unit}",
        recommendation=f"总胆固醇(TC), 高/低密度脂蛋白(HDL/LDL)使用 'cholesterol' 换算系数。"
    )