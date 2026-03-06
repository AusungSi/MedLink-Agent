# 假设您的项目结构如下:
# your_project/
# ├── engine.py  (此文件)
# ├── data_models.py
# └── formulas/
#     ├── __init__.py
#     ├── general.py  (包含 bmi, bsa, ibw)
#     ├── renal.py    (包含各种 eGFR 和 CrCl 计算)
#     ├── oncology.py (包含卡铂剂量, CCI)
#     ├── cardiology.py (包含 GRACE)
#     ├── endocrinology.py (包含糖尿病诊断, 血糖转换)
#     ├── fluid.py      (包含液体计算)
#     ├── conversions.py (包含激素, 血脂单位换算)
#     └── body_composition.py (包含体脂率计算)

from . import formulas  # 导入formulas包
from .data_models import ClinicalScoreResult
from typing import Dict, Any, Callable

class ClinicalEngine:
    def __init__(self):
        """
        初始化临床计算引擎，自动加载并注册所有可用的医学计算公式。
        """
        # 1. 创建一个“公式注册表”
        self.formula_registry: Dict[str, Callable[..., ClinicalScoreResult]] = {}
        # 2. 动态加载和注册所有公式
        self._register_formulas()
        print(f"ClinicalEngine 已成功注册 {len(self.formula_registry)} 个计算公式。")

    def _register_formulas(self):
        """
        自动扫描formulas包中的所有模块，并注册所有计算函数。
        为了清晰和可维护性，这里我们采用手动注册的方式。
        """
        # --- 通用计算 (formulas.general) ---
        self.formula_registry['bmi'] = formulas.general.calculate_bmi
        self.formula_registry['bsa'] = formulas.general.calculate_bsa
        self.formula_registry['ibw'] = formulas.general.calculate_ibw

        # --- 肾脏功能 (formulas.renal) ---
        self.formula_registry['cockcroft-gault'] = formulas.renal.calculate_cockcroft_gault
        self.formula_registry['egfr-mdrd'] = formulas.renal.calculate_egfr_mdrd
        self.formula_registry['egfr-ckd-epi'] = formulas.renal.calculate_egfr_ckd_epi
        self.formula_registry['egfr-pediatric'] = formulas.renal.calculate_pediatric_egfr_schwartz

        # --- 肿瘤学 (formulas.oncology) ---
        self.formula_registry['carboplatin-dose'] = formulas.oncology.calculate_carboplatin_dose
        self.formula_registry['charlson-cci'] = formulas.oncology.calculate_charlson_cci

        # --- 心脏病学 (formulas.cardiology) ---
        self.formula_registry['grace-score'] = formulas.cardiology.calculate_grace_score

        # --- 内分泌学 (formulas.endocrinology) ---
        self.formula_registry['diabetes-diagnosis-who'] = formulas.endocrinology.diagnose_diabetes_who

        # --- 液体管理 (formulas.fluid) ---
        self.formula_registry['maintenance-fluid'] = formulas.fluid.calculate_maintenance_fluid
        self.formula_registry['fluid-resuscitation-adult'] = formulas.fluid.calculate_fluid_resuscitation

        # --- 单位换算 (formulas.conversions) ---
        self.formula_registry['steroid-conversion'] = formulas.conversions.convert_steroid_dose
        self.formula_registry['glucose-unit-conversion'] = formulas.conversions.convert_glucose_units
        self.formula_registry['lipid-unit-conversion'] = formulas.conversions.convert_lipid_units

        # --- 身体成分 (formulas.body_composition) ---
        self.formula_registry['body-fat-from-bmi'] = formulas.body_composition.calculate_body_fat_bmi
        self.formula_registry['body-fat-from-waist'] = formulas.body_composition.calculate_body_fat_waist
        

    def list_available_formulas(self) -> Dict[str, str]:
        """
        返回所有可用公式的字典，键为公式标识符，值为其功能描述。
        这对于提供给语言模型进行工具发现至关重要。
        """
        # 函数的文档字符串 (docstring) 将作为给LLM的描述
        return {
            name: func.__doc__.strip().split('\n')[0] if func.__doc__ else "暂无描述"
            for name, func in self.formula_registry.items()
        }

    def run_calculation(self, formula_name: str, params: Dict[str, Any]) -> ClinicalScoreResult:
        """
        根据名称动态查找并执行计算。
        
        参数:
            formula_name (str): 在注册表中注册的公式的唯一标识符。
            params (Dict[str, Any]): 计算所需的参数字典。
        
        返回:
            ClinicalScoreResult: 包含计算结果、风险水平和建议的对象。
            
        异常:
            ValueError: 如果找不到指定的公式。
        """
        formula_name_lower = formula_name.lower()
        if formula_name_lower not in self.formula_registry:
            # 提供建议，以防用户输入错误
            available = ", ".join(self.formula_registry.keys())
            raise ValueError(f"不支持的计算公式: '{formula_name}'。可用公式包括: {available}")
        
        calculation_func = self.formula_registry[formula_name_lower]
        
        try:
            # 推荐: 在这里可以使用Pydantic模型对params进行严格的类型和值验证
            return calculation_func(params)
        except KeyError as e:
            # 捕获因缺少参数导致的错误
            raise ValueError(f"执行 '{formula_name}' 时缺少必要参数: {e}")
        except Exception as e:
            # 捕获并重新抛出其他计算过程中的错误
            raise RuntimeError(f"计算 '{formula_name}' 时发生错误: {e}")