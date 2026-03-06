# 🏥 医智通 (MediWise-Connect)

**基于多智能体协同的医疗辅助诊断与知识检索系统** *Intelligent Medical Multi-Agent Diagnostic & Knowledge Retrieval System*

---

## 🌟 项目简介
**医智通** 是一款面向复杂临床决策场景的智能辅助系统。它基于 **AutoGen** 多智能体框架，将本地大模型（LLM/VLM）的推理能力与严谨的医疗工作流结合，实现了从病历检索、影像分析到最终诊断报告生成的全链路自动化。

## 核心能力
* **🤖 多智能体协作**: 采用 CMO（首席医疗官）决策、Dispatcher（调度员）执行、Summarizer（总结员）整合的流水线逻辑。
* **📂 深度 RAG 支持**: 支持通用医疗知识库 (PDF) 与动态病人病历 (JSON) 的精准语义检索。
* **🖼️ 影像多模态**: 集成本地 VLM 模型，支持对医学影像（CT/X光）进行智能解读。
* **🔢 临床计算器**: 内置精确的医疗公式引擎，辅助计算风险评分与生理指标。
* **🌐 实时联网**: 通过 Tavily API 接入互联网，确保获取最新的医学进展。

## 🛠️ 快速部署
1. **环境依赖**: Python 3.10+, Ollama.
2. **启动 Ollama**: 部署 `qwen3` 和 `gemma3` 系列模型。
3. **配置项目**: 在 `src/config.py` 中填入你的向量库路径与 API Key。
4. **运行**: 启动 `session_manager.py` 开启智能诊断会话。
