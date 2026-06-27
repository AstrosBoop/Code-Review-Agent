import unittest
import tempfile
import os
from pathlib import Path
from src.database.db_manager import DBManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # 创建临时目录存放数据库
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = DBManager(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_db(self):
        """测试数据库初始化，表是否成功创建"""
        self.assertTrue(self.db_path.exists())
        
        with self.db.get_connection() as conn:
            # 检查 reviews 表
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'")
            self.assertIsNotNone(cursor.fetchone())
            
            # 检查 agent_runs 表
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agent_runs'")
            self.assertIsNotNone(cursor.fetchone())

    def test_create_and_get_review(self):
        """测试创建和获取审查记录"""
        review_id = self.db.create_review(filename="test.py", code_snippet="print('hello')")
        self.assertIsInstance(review_id, str)
        
        review = self.db.get_review(review_id)
        self.assertIsNotNone(review)
        self.assertEqual(review["filename"], "test.py")
        self.assertEqual(review["code_snippet"], "print('hello')")
        self.assertEqual(review["status"], "pending")
        # 没有 agent_runs 时应为空列表
        self.assertEqual(review["agent_runs"], [])

    def test_update_review(self):
        """测试更新审查记录"""
        review_id = self.db.create_review(filename="main.py", code_snippet="def add(a, b): return a + b")
        
        updates = {
            "score": 95,
            "risk_level": "low",
            "status": "completed",
            "report": "# Review\\nLooks good."
        }
        self.db.update_review(review_id, updates)
        
        review = self.db.get_review(review_id)
        self.assertEqual(review["score"], 95)
        self.assertEqual(review["risk_level"], "low")
        self.assertEqual(review["status"], "completed")
        self.assertEqual(review["report"], "# Review\\nLooks good.")

    def test_add_agent_run(self):
        """测试添加 Agent 运行记录，外键关联"""
        review_id = self.db.create_review(filename="sec.py", code_snippet="password = '123'")
        
        # 添加 security agent run
        run_id = self.db.add_agent_run(
            review_id=review_id,
            agent_name="security",
            status="completed",
            latency_ms=1200,
            token_input=100,
            token_output=50,
            result="Hardcoded password detected."
        )
        self.assertIsInstance(run_id, str)
        
        # 验证关联获取
        review = self.db.get_review(review_id)
        self.assertEqual(len(review["agent_runs"]), 1)
        
        agent_run = review["agent_runs"][0]
        self.assertEqual(agent_run["id"], run_id)
        self.assertEqual(agent_run["agent_name"], "security")
        self.assertEqual(agent_run["status"], "completed")
        self.assertEqual(agent_run["latency_ms"], 1200)

    def test_get_history(self):
        """测试分页获取历史"""
        # 创建 3 个 review
        for i in range(3):
            self.db.create_review(filename=f"file_{i}.py", code_snippet="")
            
        history = self.db.get_history(limit=2, offset=0)
        self.assertEqual(len(history), 2)
        
        history_page2 = self.db.get_history(limit=2, offset=2)
        self.assertEqual(len(history_page2), 1)

if __name__ == '__main__':
    unittest.main()
