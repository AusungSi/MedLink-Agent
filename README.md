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
│   └── data/
└── README.md
```

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
