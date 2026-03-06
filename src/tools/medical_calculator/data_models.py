from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# ==================== 输入模型 (Input Models) ====================

class LabResult(BaseModel):
    """代表单项化验结果。"""
    id: str = Field(..., description="化验项目的唯一标识符，例如 'wbc'")
    value: float = Field(..., description="该项结果的数值")
    unit: str = Field(..., description="测量单位，例如 'x10^9/L'")

class VitalSigns(BaseModel):
    """代表一组生命体征。"""
    temperature_celsius: Optional[float] = Field(None, description="体温 (摄氏度)")
    heart_rate_bpm: Optional[int] = Field(None, description="心率 (次/分钟)")
    respiratory_rate_bpm: Optional[int] = Field(None, description="呼吸频率 (次/分钟)")

class PatientDataSnapshot(BaseModel):
    """
    一个病人在某个时间点的数据快照，用作我们引擎的输入。
    """
    labs: List[LabResult]
    vitals: Optional[VitalSigns] = None

# ==================== 输出模型 (Output Models, 用于保证一致性) ====================

class FlaggedValue(BaseModel):
    """描述一个超出正常范围的化验值。"""
    name: str = Field(..., description="项目中文名")
    value: float
    unit: str
    status: Literal["偏高", "偏低", "危急值-高", "危急值-低"]
    normal_range: str = Field(..., description="正常值范围的文本表示")

class LabAnalysisResult(BaseModel):
    """全面的化验单分析结果。"""
    flagged_values: List[FlaggedValue]
    calculated_indices: dict[str, float] = Field(default_factory=dict, description="计算得出的指标，如阴离子间隙")
    summary: str

class SIRSResult(BaseModel):
    """SIRS评分的计算结果。"""
    score: int
    criteria_met: List[str] = Field(..., description="满足了哪些SIRS标准")
    is_positive: bool = Field(..., description="是否SIRS阳性")
    alert_message: str

class ClinicalScoreResult(BaseModel):
    """任何临床评分的通用结果模型。"""
    score_name: str
    score_value: int | float
    risk_level: str
    recommendation: str