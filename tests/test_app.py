import unittest
from fastapi.testclient import TestClient
from src.api.app import app
from src.database.db_manager import db
import time
from unittest.mock import patch

class TestApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # 每次测试前清空表
        with db.get_connection() as conn:
            conn.execute("DELETE FROM agent_runs")
            conn.execute("DELETE FROM reviews")
            conn.commit()

    @patch('src.agent.provider_adapter.default_llm.generate')
    def test_review_lifecycle(self, mock_generate):
        # 模拟 LLM 响应，防止真正的网络调用
        mock_generate.return_value = ("Mocked LLM report content", 50, 100)

        # 0. 健康检查
        resp_health = self.client.get("/api/v1/health")
        self.assertEqual(resp_health.status_code, 200)

        # 1. 提交任务
        response = self.client.post("/api/v1/review", json={
            "filename": "test.py",
            "code": "def hello(): pass"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("review_id", data)
        self.assertEqual(data["status"], "pending")
        review_id = data["review_id"]

        # 2. 由于 FastAPI 的 TestClient 默认会在同一线程执行 BackgroundTasks，
        # 所以到这一步时，后台任务实际上已经被执行完毕了！
        
        # 3. 验证获取状态 (新 status 接口)
        response_status = self.client.get(f"/api/v1/review/{review_id}/status")
        self.assertEqual(response_status.status_code, 200)
        status_data = response_status.json()
        self.assertEqual(status_data["status"], "completed")
        self.assertIn("score", status_data)
        
        # 3.1 验证获取全量报告
        response2 = self.client.get(f"/api/v1/review/{review_id}")
        self.assertEqual(response2.status_code, 200)
        review_data = response2.json()
        
        # 状态应该被置为 completed
        self.assertEqual(review_data["status"], "completed")
        self.assertIsNotNone(review_data["report"])
        self.assertIn("Mocked LLM", review_data["report"])
        
        # 验证关联的 agent_runs 被正确写入
        agent_runs = review_data["agent_runs"]
        self.assertEqual(len(agent_runs), 3) # security, quality, performance
        
        # 4. 验证历史列表
        response3 = self.client.get("/api/v1/history")
        self.assertEqual(response3.status_code, 200)
        history = response3.json()["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], review_id)

if __name__ == "__main__":
    unittest.main()
