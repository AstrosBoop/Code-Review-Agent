import unittest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from src.api.middleware import RequestIDMiddleware, setup_logger, request_id_context
from loguru import logger

class TestMiddleware(unittest.TestCase):
    def setUp(self):
        # 初始化应用和日志
        setup_logger()
        self.app = FastAPI()
        self.app.add_middleware(RequestIDMiddleware)
        
        @self.app.get("/test")
        def test_endpoint(request: Request):
            # 获取注入的 request_id
            req_id = request.headers.get("X-Request-ID")
            ctx_id = request_id_context.get()
            logger.info("Inside endpoint")
            return {"req_id": req_id, "ctx_id": ctx_id}
            
        self.client = TestClient(self.app)

    def test_request_id_injected(self):
        response = self.client.get("/test")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # 验证 contextvar 中的 ID 存在并且有值
        self.assertTrue(data["ctx_id"])
        
        # 验证返回头中包含 X-Request-ID，并且与 context 中的一致
        self.assertEqual(response.headers["X-Request-ID"], data["ctx_id"])

    def test_request_id_preserved(self):
        # 模拟客户端传入了特定的 X-Request-ID
        test_id = "test-custom-id-123"
        response = self.client.get("/test", headers={"X-Request-ID": test_id})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        # 确保中间件使用了客户端传入的 ID，而不是覆盖它
        self.assertEqual(data["ctx_id"], test_id)
        self.assertEqual(response.headers["X-Request-ID"], test_id)

if __name__ == "__main__":
    unittest.main()
