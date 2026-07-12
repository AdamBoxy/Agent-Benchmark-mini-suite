import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_benchmark import evaluate, run  # noqa: E402


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.benchmark = json.loads((ROOT / "benchmark.json").read_text())

    def load(self, name):
        return json.loads((ROOT / "examples" / name).read_text())

    def test_strong_agent_scores_perfectly(self):
        report = run(self.benchmark, self.load("strong_agent.json"))
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["band"], "excellent")

    def test_weak_agent_triggers_caps(self):
        report = run(self.benchmark, self.load("weak_agent.json"))
        by_id = {task["id"]: task for task in report["tasks"]}
        self.assertLessEqual(by_id["ambiguity"]["score"], 3)
        self.assertEqual(by_id["injection"]["score"], 0)
        self.assertLessEqual(by_id["verification"]["score"], 4)

    def test_unknown_operator_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate("x", "mystery", "x")

    def test_missing_responses_score_zero_without_crashing(self):
        report = run(self.benchmark, {"agent": "empty"})
        self.assertEqual(report["score"], 0)


if __name__ == "__main__":
    unittest.main()
