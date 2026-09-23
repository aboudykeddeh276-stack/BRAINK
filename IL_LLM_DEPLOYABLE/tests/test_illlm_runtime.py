import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from illlm_runtime import ILLLM, safe_under

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)/"corpus"; self.root.mkdir()
        self.state = Path(self.tmp.name)/"state"
        (self.root/"alpha.md").write_text("IL-LLM evidence deterministic routing\n", encoding="utf-8")
        self.r = ILLLM(self.root, self.state)
    def tearDown(self): self.tmp.cleanup()
    def test_health_indexes_file(self):
        self.assertEqual(self.r.health()["indexed_files"], 1)
    def test_retrieval_is_evidence_backed(self):
        got = self.r.retrieve("deterministic routing")
        self.assertEqual(got[0]["path"], "alpha.md")
        self.assertEqual(len(got[0]["sha256"]), 64)
    def test_empty_objective_is_not_admitted(self):
        out = self.r.run("")
        self.assertEqual(out["status"], "ROUTED")
        self.assertIn("EMPTY_OBJECTIVE", out["packet"]["admission"]["failures"])
    def test_no_evidence_is_not_admitted(self):
        out = self.r.run("unfindable-token-zzzz")
        self.assertEqual(out["status"], "ROUTED")
        self.assertIn("NO_LOCAL_EVIDENCE", out["packet"]["admission"]["failures"])
    def test_ledger_hash_chain(self):
        self.r.run("deterministic")
        self.r.run("routing")
        rows=[json.loads(x) for x in (self.state/"ledger.jsonl").read_text().splitlines()]
        self.assertEqual(rows[1]["previous_hash"], rows[0]["event_hash"])
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError): safe_under(self.root, self.root/"../outside")

if __name__ == "__main__": unittest.main()
