"""
RAG 知识库：代码规范与最佳实践
"""
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import json
from pathlib import Path
import os

# 代码规范知识库
CODE_KNOWLEDGE = [
    {
        "id": "solid_srp",
        "title": "单一职责原则（SRP）",
        "content": "每个类或函数只负责一件事。如果一个函数做了多件事，应该拆分。",
        "category": "设计原则",
        "example": "将数据获取、处理、展示分别放在不同函数中"
    },
    {
        "id": "dry",
        "title": "DRY 原则（Don't Repeat Yourself）",
        "content": "避免重复代码。相同逻辑出现两次以上，应提取为公共函数或类。",
        "category": "设计原则",
        "example": "将多处重复的数据校验逻辑提取为 validate() 函数"
    },
    {
        "id": "naming_convention",
        "title": "命名规范",
        "content": "Python 中函数和变量用 snake_case，类用 PascalCase，常量用 UPPER_CASE。名字要有意义，避免单字母变量（循环变量除外）。",
        "category": "代码规范",
        "example": "用 user_name 而不是 n，用 MAX_RETRY_COUNT 而不是 3"
    },
    {
        "id": "error_handling",
        "title": "异常处理规范",
        "content": "捕获具体的异常类型而非 Exception 或裸 except。异常处理后要有明确的处理逻辑，不要只是 pass。",
        "category": "健壮性",
        "example": "except ValueError as e: 而不是 except:"
    },
    {
        "id": "function_length",
        "title": "函数长度控制",
        "content": "函数建议不超过 30 行，超过 50 行必须考虑拆分。长函数难以测试和维护。",
        "category": "可维护性",
        "example": "将一个 100 行的处理函数拆分为 parse()、validate()、transform() 三个小函数"
    },
    {
        "id": "sql_injection",
        "title": "SQL 注入防护",
        "content": "永远不要用字符串拼接构造 SQL 语句。使用参数化查询或 ORM 框架。",
        "category": "安全",
        "example": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"
    },
    {
        "id": "secret_management",
        "title": "密钥管理",
        "content": "密码、API Key、Token 等敏感信息不能硬编码在代码中，应存储在环境变量或配置文件（加入 .gitignore）中。",
        "category": "安全",
        "example": "api_key = os.getenv('API_KEY') 而不是 api_key = 'sk-abc123'"
    },
    {
        "id": "list_comprehension",
        "title": "列表推导式",
        "content": "Python 中列表推导式比 for 循环 + append 性能更好，也更 Pythonic。但不要过度嵌套，超过两层嵌套就应改回 for 循环。",
        "category": "性能",
        "example": "result = [x*2 for x in data if x > 0] 替代 for 循环"
    },
    {
        "id": "type_hints",
        "title": "类型注解",
        "content": "Python 3.5+ 支持类型注解，为函数参数和返回值添加类型注解可以提高代码可读性，并支持静态分析工具检查。",
        "category": "可读性",
        "example": "def process(data: list[str]) -> dict:"
    },
    {
        "id": "docstring",
        "title": "文档字符串",
        "content": "公共函数和类应该有 docstring，说明功能、参数、返回值。私有函数视复杂度决定是否添加。",
        "category": "文档",
        "example": '"""计算用户年龄\\n\\nArgs:\\n    birth_year: 出生年份\\nReturns:\\n    int: 年龄\\n"""'
    },
    {
        "id": "global_variable",
        "title": "避免全局变量",
        "content": "全局变量使代码难以测试和维护，多个函数共享状态容易产生 bug。应将状态封装到类中，或通过函数参数传递。",
        "category": "可维护性",
        "example": "将全局配置封装到 Config 类中"
    },
    {
        "id": "magic_number",
        "title": "消除魔法数字",
        "content": "代码中直接出现的数字（除 0 和 1 外）应定义为有意义的常量，提高可读性和可维护性。",
        "category": "可读性",
        "example": "MAX_CONNECTIONS = 100 而不是直接写 100"
    },
]


class CodeKnowledgeBase:
    """代码规范 RAG 知识库"""

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2", lazy_load: bool = False):
        self.embedding_model = embedding_model
        self.encoder = None if lazy_load else SentenceTransformer(embedding_model, local_files_only=True)
        self.index = None
        self.documents = []

    def build(self, save_path: str = "data/processed/vector_db"):
        """构建向量索引"""
        self.documents = []
        for item in CODE_KNOWLEDGE:
            text = f"{item['title']}: {item['content']}"
            self.documents.append({"id": item["id"], "text": text, "info": item})

        if self.encoder is None:
            self.encoder = SentenceTransformer(self.embedding_model, local_files_only=True)

        texts = [doc["text"] for doc in self.documents]
        embeddings = self.encoder.encode(texts)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype("float32"))

        Path(save_path).mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, f"{save_path}/index.faiss")
        with open(f"{save_path}/documents.json", "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        print(f"知识库构建完成，共 {len(self.documents)} 条记录")

    def load(self, load_path: str = "data/processed/vector_db"):
        """从磁盘加载索引"""
        index_path = f"{load_path}/index.faiss"
        doc_path = f"{load_path}/documents.json"
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"索引文件不存在: {load_path}")
        self.index = faiss.read_index(index_path)
        with open(doc_path, "r", encoding="utf-8") as f:
            self.documents = json.load(f)
        print(f"知识库加载完成，共 {len(self.documents)} 条记录")

    def retrieve(self, query: str, top_k: int = 3) -> list:
        """检索相关知识"""
        if self.encoder is None:
            self.encoder = SentenceTransformer(self.embedding_model, local_files_only=True)
        query_vec = self.encoder.encode([query])
        distances, indices = self.index.search(query_vec.astype("float32"), top_k)
        return [{"document": self.documents[idx], "distance": float(dist)}
                for idx, dist in zip(indices[0], distances[0])]


if __name__ == "__main__":
    kb = CodeKnowledgeBase()
    kb.build()
    results = kb.retrieve("SQL 注入安全问题")
    print("\n检索测试:")
    for r in results:
        print(f"- {r['document']['info']['title']}: {r['document']['info']['content'][:40]}...")
