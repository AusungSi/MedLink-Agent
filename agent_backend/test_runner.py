# 文件路径: test_runner.py
# 【重构版：带最终总结报告】

import requests
import json
import time
import websocket
from threading import Thread
from typing import List, Dict, Any, Tuple

BASE_URL = "http://127.0.0.1:8000"

# --- 全局变量，用于存储所有测试的结果 ---
test_results = []

# --- 辅助函数 ---

def run_agent_test_case(test_name: str, question: str, timeout: int = 120) -> Tuple[bool, str, str]:
    """
    运行一个Agent测试用例，并返回一个包含结果的元组。
    返回: (is_success, summary_message, full_log)
    """
    print(f"\n{'='*20} [RUNNING] {test_name.upper()} {'='*20}")
    print(f"QUESTION: \"{question}\"")
    
    full_conversation_log = []
    log_capture = []

    try:
        start_response = requests.post(f"{BASE_URL}/api/v1/chat/start", json={"question": question})
        start_response.raise_for_status()
        session_id = start_response.json()["session_id"]
    except requests.exceptions.RequestException as e:
        error_msg = f"Error starting chat session: {e}"
        log_capture.append(f"!!! [FAIL] {error_msg}")
        return False, error_msg, "\n".join(log_capture)

    ws_url = f"ws://127.0.0.1:8000/api/v1/chat/ws/{session_id}"
    
    def on_message(ws, message):
        msg_data = json.loads(message)
        formatted_msg = f"<<< MSG from {msg_data.get('speaker', 'System')}: {json.dumps(msg_data, ensure_ascii=False, indent=2)}"
        print(formatted_msg)
        log_capture.append(formatted_msg)
        full_conversation_log.append(msg_data)

    def on_error(ws, error):
        log_capture.append(f"!!! WebSocket Error: {error}")

    ws_app = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error)
    wst = Thread(target=ws_app.run_forever)
    wst.daemon = True
    wst.start()
    wst.join(timeout=timeout)
    
    if wst.is_alive():
        timeout_msg = f"Test case did not finish within the {timeout}s time limit."
        log_capture.append(f"!!! [TIMEOUT] {timeout_msg}")
        ws_app.close()
        return False, timeout_msg, "\n".join(log_capture)

    print(f"--- [FINISHED] {test_name.upper()} ---")
    
    history_str = json.dumps(full_conversation_log, ensure_ascii=False)
    return True, "Agent conversation completed.", history_str


def verify_tool_call(history: str, tool_name: str) -> Tuple[bool, str]:
    """检查对话历史，并返回验证结果。"""
    if f'"name": "{tool_name}"' in history:
        msg = f"Tool '{tool_name}' was called successfully."
        return True, msg
    else:
        msg = f"Tool '{tool_name}' was NOT called."
        return False, msg

# --- 测试函数定义 ---

def test_0_fixed_services():
    """测试固定的API服务，并将结果存入全局列表。"""
    test_name = "Fixed Services"
    print(f"\n{'='*20} [RUNNING] {test_name.upper()} {'='*20}")
    
    # 子测试1: Imaging Summary
    sub_test_name_1 = "Imaging Summary Service"
    try:
        response = requests.post(f"{BASE_URL}/api/v1/imaging/summary", json={"patient_name": "张三", "body_part": "胸部"})
        response.raise_for_status()
        test_results.append({"name": sub_test_name_1, "status": "PASS", "details": "Service responded successfully."})
    except Exception as e:
        test_results.append({"name": sub_test_name_1, "status": "FAIL", "details": str(e)})

    # 子测试2: Medical Record Generation
    sub_test_name_2 = "Medical Record Generation Service"
    try:
        response = requests.post(f"{BASE_URL}/api/v1/medical_record/generate", json={"patient_name": "张三"})
        response.raise_for_status()
        data = response.json()
        if "patient_name" in data and "encounters" in data:
            test_results.append({"name": sub_test_name_2, "status": "PASS", "details": "Service responded with a valid JSON structure."})
        elif "error" in data:
            details = f"Service returned an error payload. Raw output: {data.get('raw_output', 'N/A')}"
            test_results.append({"name": sub_test_name_2, "status": "FAIL", "details": details})
        else:
            details = f"Returned JSON is invalid. Content: {json.dumps(data, ensure_ascii=False)}"
            test_results.append({"name": sub_test_name_2, "status": "FAIL", "details": details})
    except Exception as e:
        test_results.append({"name": sub_test_name_2, "status": "FAIL", "details": str(e)})
    
    print(f"--- [FINISHED] {test_name.upper()} ---")


def run_and_log_agent_test(test_name, question, tool_to_verify):
    """一个包装器，运行Agent测试并记录结果。"""
    is_success, summary, history = run_agent_test_case(test_name, question)
    if not is_success:
        test_results.append({"name": test_name, "status": "FAIL", "details": summary, "log": history})
        return

    verified, details = verify_tool_call(history, tool_to_verify)
    if verified:
        test_results.append({"name": test_name, "status": "PASS", "details": details})
    else:
        test_results.append({"name": test_name, "status": "FAIL", "details": details, "log": history})


def run_complex_agent_test(test_name, question, tools_to_verify):
    """为复杂场景设计的包装器。"""
    is_success, summary, history = run_agent_test_case(test_name, question, timeout=180)
    if not is_success:
        test_results.append({"name": test_name, "status": "FAIL", "details": summary, "log": history})
        return
        
    all_verified = True
    details_list = []
    for tool in tools_to_verify:
        verified, details = verify_tool_call(history, tool)
        if not verified:
            all_verified = False
        details_list.append(details)
    
    final_details = "\n".join(details_list)
    if all_verified:
        test_results.append({"name": test_name, "status": "PASS", "details": final_details})
    else:
        test_results.append({"name": test_name, "status": "FAIL", "details": final_details, "log": history})


# --- 总结报告函数 ---

def print_summary_report():
    """在所有测试结束后，打印格式化的总结报告。"""
    print("\n\n" + "="*80)
    print(" " * 30 + "TEST SUMMARY REPORT")
    print("="*80)

    passed_count = 0
    failed_tests = []

    for result in test_results:
        if result["status"] == "PASS":
            passed_count += 1
        else:
            failed_tests.append(result)

    print(f"Total Tests Run: {len(test_results)}")
    print(f"  - Passed: {passed_count}")
    print(f"  - Failed: {len(failed_tests)}")
    print("-" * 80)

    if not failed_tests:
        print("\n🎉 ALL TESTS PASSED! 🎉")
    else:
        print("\n🚨 FAILED TESTS DETAILS 🚨\n")
        for i, failure in enumerate(failed_tests, 1):
            print(f"--- Failure #{i}: {failure['name']} ---")
            print(f"  [REASON]: {failure['details']}")
            if "log" in failure:
                print("  [FULL LOG]:")
                # 缩进日志，方便阅读
                log_lines = failure['log'].split('\n')
                for line in log_lines:
                    print(f"    {line}")
            print("-" * 50 + "\n")
    
    print("="*80)


if __name__ == "__main__":
    print("Waiting 3 seconds for the server to fully start...")
    time.sleep(3)

    # --- 执行所有测试 ---
    test_0_fixed_services()
    
    run_and_log_agent_test("Unit Test: list_available_calculations", "有哪些可用的计算公式？", "list_available_calculations")
    run_and_log_agent_test("Unit Test: run_clinical_calculation", "身高1.75米，体重70公斤，请计算BMI。", "run_clinical_calculation")
    run_and_log_agent_test("Unit Test: retrieve_patient_records", "查询'李四'的病历。", "retrieve_patient_records")
    run_and_log_agent_test("Unit Test: retrieve_context_from_db (RAG)", "高血压的诊断标准是什么？", "retrieve_context_from_db")
    run_and_log_agent_test("Unit Test: search_web", "搜索2025年阿尔茨海默病治疗进展。", "search_web")
    run_and_log_agent_test("Unit Test: generate_report_from_image", "根据图片 './test_images/chest_xray.png' 生成诊断报告。", "generate_report_from_image")
    
    run_complex_agent_test(
        "Complex Scenario: Kidney Function Assessment",
        "评估病人'李四'的肾功能。先查他的病历找到年龄、体重和肌酐值，然后用'cockcroft-gault'公式计算肌酐清除率。",
        ["retrieve_patient_records", "run_clinical_calculation"]
    )
    
    # --- 在所有测试结束后打印总结报告 ---
    print_summary_report()