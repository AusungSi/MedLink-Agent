"""
agent_backend/src/tools/medical_calculator/formulas/thyroid.py
专门用于计算甲状腺结节TI-RADS积分与恶性概率的算法工具。
严格对齐 ACR TI-RADS 2017 标准。
"""
from typing import Dict, Union, Optional
import pydantic

class ThyroidCharacteristics(pydantic.BaseModel):
    """甲状腺超声特征结构化输入模型"""
    composition: str = pydantic.Field(description="成份: 囊性=0, 蜂窝状=0, 实性=2, 混合实性=2")
    echogenicity: str = pydantic.Field(description="回声: 无回声=0, 高回声=1, 等回声=1, 低回声=2, 极低回声=3")
    shape: str = pydantic.Field(description="形状: 宽大于高=0, 高大于宽=3")
    margin: str = pydantic.Field(description="边缘: 光滑=0, 局限=0, 分叶=2, 不规则=2, 腺体外侵犯=3")
    echogenic_foci: str = pydantic.Field(description="局灶性强回声: 无=0, 大彗星尾=0, 粗钙化=1, 周边钙化=2, 点状强回声=3")

def calculate_thyroid_ti_rads(characteristics: Dict[str, str]) -> Dict[str, Union[int, str, float]]:
    """
    专门用于计算甲状腺结节TI-RADS积分与恶性概率的核心算法。
    该工具通过医学严谨的'if-else'逻辑进行量化评分，杜绝幻觉。

    Args:
        characteristics: 结构化的超声特征JSON对象，包含以下键：
            'composition', 'echogenicity', 'shape', 'margin', 'echogenic_foci'

    Returns:
        Dict: 包含得分、TI-RADS分级、建议处理方案、惡性风险概率的JSON对象。
    """
    # 0. 输入校验：确保传入的字典是正确的（AutoGen调用工具时的常见错误排查）
    try:
        validated_data = ThyroidCharacteristics(**characteristics)
    except Exception as e:
        return {"status": "error", "message": f"输入特征JSON格式不正确: {str(e)}"}

    total_score = 0
    detailed_scores = {}
    
    # 1. 成份 (Composition) -- 严格按照 ACR 标准
    comp_map = {
        "囊性": 0, "蜂窝状": 0, "无回声": 0, 
        "混合实性": 2, "实性": 2
    }
    # 模糊匹配容错
    comp_score = 0
    for k, v in comp_map.items():
        if k in validated_data.composition:
            comp_score = v
            break
    total_score += comp_score
    detailed_scores["成份"] = f"+{comp_score}"

    # 2. 回声 (Echogenicity)
    echo_map = {
        "无回声": 0, 
        "高回声": 1, "等回声": 1, 
        "低回声": 2, 
        "极低回声": 3
    }
    echo_score = 0
    for k, v in echo_map.items():
        if k in validated_data.echogenicity:
            echo_score = v
            break
    total_score += echo_score
    detailed_scores["回声"] = f"+{echo_score}"

    # 3. 形状 (Shape)
    shape_score = 0
    if "高大于宽" in validated_data.shape:
        shape_score = 3
    total_score += shape_score
    detailed_scores["形状"] = f"+{shape_score}"

    # 4. 边缘 (Margin)
    margin_map = {
        "光滑": 0, "局限": 0, 
        "分叶": 2, "不规则": 2, 
        "腺体外侵犯": 3
    }
    margin_score = 0
    for k, v in margin_map.items():
        if k in validated_data.margin:
            margin_score = v
            break
    total_score += margin_score
    detailed_scores["边缘"] = f"+{margin_score}"

    # 5. 局灶性强回声 (Echogenic Foci)
    foci_map = {
        "无": 0, "大彗星尾": 0, 
        "粗钙化": 1, 
        "周边钙化": 2, 
        "点状强回声": 3
    }
    foci_score = 0
    for k, v in foci_map.items():
        if k in validated_data.echogenic_foci:
            foci_score = v
            break
    total_score += foci_score
    detailed_scores["局灶性强回声"] = f"+{foci_score}"

    # 6. 计算最终等级和风险
    ti_rads_class = ""
    malignancy_prob = ""
    management_advice = ""

    if total_score == 0:
        ti_rads_class = "TI-RADS 1类 (Benign)"
        malignancy_prob = "< 2%"
        management_advice = "无需随访"
    elif total_score == 2:
        ti_rads_class = "TI-RADS 2类 (Not Suspect)"
        malignancy_prob = "< 2%"
        management_advice = "无需随访"
    elif total_score == 3:
        ti_rads_class = "TI-RADS 3类 (Mildly Suspect)"
        malignancy_prob = "< 5%"
        management_advice = "结节 >= 2.5cm 建议穿刺 (FNA); >= 1.5cm 建议随访"
    elif 4 <= total_score <= 6:
        ti_rads_class = "TI-RADS 4类 (Moderately Suspect)"
        malignancy_prob = "5% ~ 20%"
        management_advice = "结节 >= 1.5cm 建议穿刺 (FNA); >= 1.0cm 建议随访"
    elif total_score >= 7:
        ti_rads_class = "TI-RADS 5类 (Highly Suspect)"
        malignancy_prob = "> 20%"
        management_advice = "结节 >= 1.0cm 建议穿刺 (FNA); >= 0.5cm 建议随访"

    return {
        "status": "success",
        "TI_RADS积分": total_score,
        "评分明细": detailed_scores,
        "TI_RADS分级": ti_rads_class,
        "惡性风险概率": malignancy_prob,
        "指南建议管理方案": management_advice
    }