import json
import logging
import requests
from ..config import TAVILY_API_KEY



def search_web(query: str) -> str:
    """使用Tavily API执行网页搜索，用于查询最新的医学研究、新闻或罕见病信息。"""
    logging.info(f"正在执行网页搜索，查询: '{query}'")
    api_url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": 5,
    }
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return "网页搜索没有返回任何结果。"
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"错误：执行网页搜索时发生错误: {e}"
