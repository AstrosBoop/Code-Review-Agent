import unittest
from unittest.mock import patch
import time
from src.agent.reviewer_graph import build_review_graph

class TestReviewerGraph(unittest.TestCase):
    def setUp(self):
        self.graph = build_review_graph()

    @patch('src.agent.provider_adapter.default_llm.generate')
    def test_graph_execution(self, mock_generate):
        # 模拟 LLM 响应 (返回: content, input_tokens, output_tokens)
        mock_generate.return_value = ("Mocked LLM report content", 10, 20)

        initial_state = {
            "code": "def hello(): pass",
            "filename": "test.py",
            "metrics": {"workflow_start_time": time.time()}
        }

        # 运行图
        final_state = self.graph.invoke(initial_state)

        # 验证所有节点是否如期执行
        self.assertIn("static_results", final_state)
        self.assertIn("rag_context", final_state)
        self.assertIn("security_report", final_state)
        self.assertIn("quality_report", final_state)
        self.assertIn("performance_report", final_state)
        self.assertIn("final_report", final_state)
        
        # 验证 LLM 被调用了 4 次 (3个并行reviewer + 1个synthesizer)
        self.assertEqual(mock_generate.call_count, 4)
        
        # 验证 metrics 是否被收集
        metrics = final_state.get("metrics", {})
        self.assertIn("security_tokens_in", metrics)
        self.assertIn("total_workflow_time", metrics)

if __name__ == '__main__':
    unittest.main()
