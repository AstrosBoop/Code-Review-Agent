import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# 默认将数据库文件放在项目根目录下的 data 文件夹
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "code_review.db"

from contextlib import closing

class DBManager:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self):
        """获取带列名访问的数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return closing(conn)

    def init_db(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建 reviews 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id VARCHAR(36) PRIMARY KEY,
                    created_at DATETIME NOT NULL,
                    filename VARCHAR(255),
                    code_snippet TEXT,
                    score INTEGER,
                    risk_level VARCHAR(10),
                    report TEXT,
                    status VARCHAR(20),
                    total_latency_ms INTEGER
                )
            ''')
            
            # 创建 agent_runs 表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id VARCHAR(36) PRIMARY KEY,
                    review_id VARCHAR(36) NOT NULL,
                    agent_name VARCHAR(50) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    latency_ms INTEGER,
                    token_input INTEGER,
                    token_output INTEGER,
                    result TEXT,
                    error_message TEXT,
                    FOREIGN KEY (review_id) REFERENCES reviews (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()

    def create_review(self, filename: str, code_snippet: str) -> str:
        """
        创建一个新的审查记录，初始状态为 'pending'
        返回新记录的 id
        """
        review_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO reviews (id, created_at, filename, code_snippet, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (review_id, created_at, filename, code_snippet, "pending"))
            conn.commit()
            
        return review_id

    def update_review(self, review_id: str, updates: Dict[str, Any]):
        """
        更新审查记录
        updates 是一个字典，包含需要更新的字段，例如：
        {"score": 85, "risk_level": "low", "status": "completed", "total_latency_ms": 1200}
        """
        if not updates:
            return

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        values.append(review_id)
        
        with self.get_connection() as conn:
            conn.execute(f'''
                UPDATE reviews
                SET {set_clause}
                WHERE id = ?
            ''', values)
            conn.commit()

    def add_agent_run(self, review_id: str, agent_name: str, status: str, 
                      latency_ms: Optional[int] = None, token_input: Optional[int] = None, 
                      token_output: Optional[int] = None, result: Optional[str] = None, 
                      error_message: Optional[str] = None) -> str:
        """记录单个 Agent 的运行结果"""
        run_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO agent_runs 
                (id, review_id, agent_name, status, latency_ms, token_input, token_output, result, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (run_id, review_id, agent_name, status, latency_ms, token_input, token_output, result, error_message))
            conn.commit()
            
        return run_id

    def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """获取单个审查报告及其所有的 agent runs"""
        with self.get_connection() as conn:
            # 获取主报告
            cursor = conn.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
            row = cursor.fetchone()
            if not row:
                return None
                
            review = dict(row)
            
            # 获取相关的 agent_runs
            cursor = conn.execute('SELECT * FROM agent_runs WHERE review_id = ?', (review_id,))
            review['agent_runs'] = [dict(r) for r in cursor.fetchall()]
            
            return review

    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """获取历史审查记录列表，按时间倒序"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, created_at, filename, score, risk_level, status, total_latency_ms 
                FROM reviews 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(r) for r in cursor.fetchall()]

# 默认的全局 DBManager 实例
db = DBManager()
