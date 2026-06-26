"""
Gradio Web 界面
"""
import gradio as gr
from pathlib import Path
import sys
import os
import tempfile

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

sys.path.append(str(Path(__file__).parent / "src"))

from rag.knowledge_base import CodeKnowledgeBase
from agent.reviewer import CodeReviewAgent
from agent.reviewer_langchain import CodeReviewAgentLC

# 示例代码
EXAMPLE_CODE = '''import sqlite3
import hashlib

password = "admin123"
db_conn = sqlite3.connect("users.db")

def get_user(username):
    cursor = db_conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()

def hash_password(pwd):
    return hashlib.md5(pwd.encode()).hexdigest()

def process_users(user_list):
    result = []
    for user in user_list:
        data = get_user(user)
        if data:
            result.append(data)
    return result
'''


def load_agent():
    print("正在加载模型...")
    kb = CodeKnowledgeBase(lazy_load=True)
    kb.load(str(Path(__file__).parent / "data/processed/vector_db"))
    from sentence_transformers import SentenceTransformer
    kb.encoder = SentenceTransformer(kb.embedding_model, local_files_only=True)
    agent_original = CodeReviewAgent(kb, provider="deepseek")
    agent_lc = CodeReviewAgentLC(kb, provider="deepseek")
    print("模型加载完成!")
    return agent_original, agent_lc


def review_code(code: str, mode: str):
    if not code or not code.strip():
        return "请输入需要审查的代码", None
    try:
        current_agent = agent_lc if mode == "LangChain 版" else agent_original
        result = current_agent.review(code)
        report = result["report"]
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write(report)
        tmp.close()
        return report, tmp.name
    except Exception as e:
        return f"审查失败: {str(e)}", None


# 全局加载
try:
    agent_original, agent_lc = load_agent()
except Exception as e:
    print(f"模型加载失败: {e}")
    agent_original, agent_lc = None, None


with gr.Blocks(title="智能代码审查 Agent") as demo:
    gr.Markdown("# 🤖 智能代码审查 Agent")
    gr.Markdown("基于 LLM Function Calling + RAG 的自动化代码审查系统")

    with gr.Row():
        with gr.Column(scale=1):
            code_input = gr.Code(
                label="输入代码",
                language="python",
                value=EXAMPLE_CODE,
                lines=25
            )
            mode_selector = gr.Radio(
                choices=["原版 (OpenAI SDK)", "LangChain 版"],
                value="原版 (OpenAI SDK)",
                label="Agent 实现版本"
            )
            review_btn = gr.Button("开始审查", variant="primary", size="lg")

        with gr.Column(scale=1):
            report_output = gr.Markdown(label="审查报告")
            download_btn = gr.File(label="下载报告 (.md)", visible=False)

    review_btn.click(
        fn=review_code,
        inputs=[code_input, mode_selector],
        outputs=[report_output, download_btn]
    ).then(
        fn=lambda path: gr.File(visible=path is not None),
        inputs=[download_btn],
        outputs=[download_btn]
    )

    gr.Markdown("""
    ## 使用说明
    1. 在左侧输入需要审查的代码（支持 Python）
    2. 点击「开始审查」按钮
    3. Agent 将自动调用多个工具进行分析，并生成报告

    ## 审查内容
    - **代码质量**：函数长度、命名规范、注释覆盖率、魔法数字
    - **安全漏洞**：SQL 注入、硬编码密钥、命令注入、弱加密等
    - **优化建议**：性能优化、可维护性改进
    - **最佳实践**：基于 RAG 知识库检索相关规范
    """)


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7861,
        share=False,
        show_error=True
    )
