# medical_qa

## 项目结构

```text
medical_qa/
├── backend/               # Web 后端 (Flask)
├── frontend/              # Web 前端 (静态页面)
├── agent_backend/         # AI Agent 后端 (FastAPI + AutoGen)
│   ├── server.py
│   ├── services/
│   ├── src/
│   ├── data/
│   └── autogen_compat/    # 从 medical_qa_autogen 合并的兼容脚本/依赖
└── README.md
```

## 合并说明

- 当前仓库已合并 `/root/medical_qa` 与 `/root/medical_qa_autogen` 的代码内容。
- `medical_qa_autogen` 中的兼容资源已放入 `agent_backend/autogen_compat/`。
- 大体积模型和向量库文件（如 `.gguf`、`vector_db/`）未纳入仓库，避免仓库膨胀。

## 启动方式

### 1) Web 后端 (Flask)

```bash
cd /root/medical_qa/backend
pip install -r requirements.txt
export FLASK_APP=manage.py
flask run --host 0.0.0.0 --port 5000
```

### 2) Web 前端

```bash
cd /root/medical_qa/frontend
python -m http.server 5173
```

### 3) AI Agent 后端 (FastAPI)

```bash
cd /root/medical_qa
uvicorn agent_backend.server:app --host 0.0.0.0 --port 8000 --reload
```
