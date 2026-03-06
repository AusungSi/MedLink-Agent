# filename: formulas/fluid.py

from ..data_models import ClinicalScoreResult
from typing import Dict, Any

def calculate_maintenance_fluid(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算每日维持液体量 (Holliday-Segar法)。需要: weight_kg(体重kg)。
    """
    weight = params['weight_kg']
    if weight <= 0:
        raise ValueError("体重必须是正数。")

    daily_fluid_ml = 0
    
    if weight <= 10:
        # 首10kg: 100 mL/kg
        daily_fluid_ml = weight * 100
    elif weight <= 20:
        # 中间10kg: 50 mL/kg
        daily_fluid_ml = (10 * 100) + ((weight - 10) * 50)
    else:
        # 超过20kg的部分: 20 mL/kg
        daily_fluid_ml = (10 * 100) + (10 * 50) + ((weight - 20) * 20)
        
    hourly_rate_ml = daily_fluid_ml / 24
    
    daily_fluid_rounded = round(daily_fluid_ml, 2)
    hourly_rate_rounded = round(hourly_rate_ml, 2)

    return ClinicalScoreResult(
        score_name="每日维持液体量",
        score_value=daily_fluid_rounded,
        risk_level=f"{daily_fluid_rounded} mL/天 (或 {hourly_rate_rounded} mL/小时)",
        recommendation="这是标准生理状况下的基础液体需求。在发热、呕吐、腹泻或高代谢状态下需要酌情增加。该公式主要用于儿科，但在成人中也可作为基准参考。"
    )

def calculate_fluid_resuscitation(params: Dict[str, Any]) -> ClinicalScoreResult:
    """
    计算成人脱水补液量。需要: weight_kg(体重kg), percent_dehydration(脱水百分比，如5%输入5)。
    """
    weight = params['weight_kg']
    percent_dehydration = params['percent_dehydration']
    
    if weight <= 0 or not (0 < percent_dehydration < 100):
        raise ValueError("体重必须为正数，脱水百分比应在0到100之间。")

    # 液体亏损量 (L) = 体重 (kg) * 脱水百分比 (%)
    # 液体亏损量 (mL) = 体重 (kg) * (脱水百分比 / 100) * 1000
    fluid_deficit_ml = weight * percent_dehydration * 10
    fluid_deficit_rounded = round(fluid_deficit_ml, 2)
    
    recommendation = (
        f"总液体亏损量为 {fluid_deficit_rounded} mL。 "
        "此为需要补充的累积丢失量，不包括每日维持量和持续丢失量。 "
        "通常建议在24小时内补完，其中一半（约{round(fluid_deficit_rounded/2, 2)} mL）在最初的8小时内补给，具体速度需根据患者的血流动力学状态和临床反应进行调整。"
    )

    return ClinicalScoreResult(
        score_name="成人脱水补液量",
        score_value=fluid_deficit_rounded,
        risk_level=f"液体亏损: {fluid_deficit_rounded} mL",
        recommendation=recommendation
    )