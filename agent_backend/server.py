# 【新增/替换代码】
import asyncio
from fastapi import FastAPI, WebSocket, Depends, WebSocketDisconnect
from pydantic import BaseModel
import chromadb

# 导入服务和内核管理器
from agent_backend.services import imaging_service, medical_record_service
from agent_backend.src.autogen_kernel import session_manager
# --- 导入ToolExecutor ---
from agent_backend.src.autogen_kernel.agents import setup_agent_tools, ToolExecutor
from agent_backend.src.rag_utils import RagUtils
from agent_backend.src.tools.medical_calculator.engine import ClinicalEngine
from agent_backend.src.config import VECTOR_DB_PATH, KNOWLEDGE_BASE_PATH

app = FastAPI(title="Medical AI Assistant Backend")

# --- 依赖注入和启动事件 ---

# 1. 在全局范围内创建所有依赖的单例实例
rag_util_instance = RagUtils(ollama_model_name="bge_zh:latest", db_path=VECTOR_DB_PATH, source_dir=KNOWLEDGE_BASE_PATH)
in_memory_client_instance = chromadb.Client()
clinical_engine_instance = ClinicalEngine()

# 2. 用这些实例来创建ToolExecutor的单例实例
tool_executor_instance = ToolExecutor(
    rag_util=rag_util_instance,
    in_memory_client=in_memory_client_instance,
    clinical_engine=clinical_engine_instance
)

# 3. 在应用启动时，将这个单一的实例传递给 setup_agent_tools
@app.on_event("startup")
def startup_event():
    """应用启动时，传入完整的ToolExecutor实例来设置Agent工具。"""
    setup_agent_tools(tool_executor_instance)
    print("FastAPI server started and AutoGen tools are configured.")

# --- API 路由部分 ---

# 我们可以为ToolExecutor也创建一个依赖注入函数，方便在路由中使用
def get_tool_executor():
    return tool_executor_instance

# --- 路径一：结构化服务 API ---
class ImagingSummaryRequest(BaseModel):
    patient_name: str
    body_part: str

@app.post("/api/v1/imaging/summary", tags=["Structured Services"])
async def get_imaging_summary(request: ImagingSummaryRequest, executor: ToolExecutor = Depends(get_tool_executor)):
    # 注意这里我们注入了executor，并传递给服务函数
    result = imaging_service.run_imaging_summary_workflow(
        patient_name=request.patient_name,
        body_part=request.body_part,
        tool_executor=executor # 传递依赖
    )
    return result

class MedicalRecordRequest(BaseModel):
    patient_name: str
    chat_context: str  # 【新增】接收前端传来的对话上下文

@app.post("/api/v1/medical_record/generate", tags=["Structured Services"])
async def generate_medical_record(request: MedicalRecordRequest, executor: ToolExecutor = Depends(get_tool_executor)):
    """
    接收病人姓名，调用专用的AutoGen工作流生成结构化的JSON病历。
    这是一个同步的、可预测的接口。
    """
    # 注意：这个调用是阻塞的，FastAPI会等待它完成后再返回响应。
    # 这对于生成固定文档的场景是合适的。
    result = medical_record_service.run_record_generation_workflow(
        patient_name=request.patient_name,
        chat_context=request.chat_context,
        tool_executor=executor
    )
    return result

# --- 路径二：动态代理 API ---
class StartChatRequest(BaseModel):
    question: str

@app.post("/api/v1/chat/start", tags=["Dynamic Agent"])
async def start_chat(request: StartChatRequest):
    session_id = session_manager.create_new_session()
    session = session_manager.get_session(session_id)
    asyncio.create_task(session.start_chat(request.question))
    return {"session_id": session_id}

@app.websocket("/api/v1/chat/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=1008, reason="Invalid session ID")
        return

    session_finished = False
    try:
        # 只要会话没有确认结束，就持续循环
        while not session_finished:
            
            # 在一次循环中，处理掉当前队列里的所有消息
            # 这样可以确保不会因为 asyncio.sleep 的延迟而错过消息
            while not session.queue.empty():
                message = session.queue.get_nowait()
                
                # 发送消息
                await websocket.send_json(message)
                
                # 检查是否是结束或错误信号
                if message.get("type") in ["session_end", "error"]:
                    session_finished = True
                    # 收到结束信号后，跳出内层循环
                    # 外层循环的条件也将变为False，从而自然退出
                    break
            
            # 如果会话还未结束，但队列暂时为空，
            # 则短暂挂起，让出CPU给其他任务，避免空转
            if not session_finished:
                await asyncio.sleep(0.1)
    
    except WebSocketDisconnect:
        print(f"Client for session {session_id} disconnected.")
    finally:
        # 确保 WebSocket 连接被关闭
        # 虽然FastAPI通常会自动处理，但明确关闭是好习惯
        await websocket.close() 
        if session_id in session_manager.SESSIONS:
            session_manager.SESSIONS.pop(session_id, None)
            print(f"Session {session_id} closed and cleaned up.")
