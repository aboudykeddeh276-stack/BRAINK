from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from src.keddeh_product_runtime import load_product,run_product
class ProductRuntimeTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);(self.root/"config").mkdir();(self.root/"src").mkdir();(self.root/"dashboard").mkdir();(self.root/"dashboard"/"index.html").write_text("ok");(self.root/"src"/"module.py").write_text("x=1")
  r={"products":[{"applicationId":"test.application","kind":"APPLICATION","entrypoint":"dashboard/index.html","runtime":"BROWSER_ESM","route":"/test","vfsNamespace":"vfs://apps/test.application/","suppliedCapabilities":["TEST"],"modules":["src/module.py"],"criticality":"CORE_DEGRADED","fallbackAdapter":"adapter.test","launchCommand":"unused","testCommand":"python3 -c 'print(1)'","deploymentTarget":"PORTABLE","maturity":"IMPLEMENTED"}]};(self.root/"config"/"kapp_product_registry.json").write_text(json.dumps(r))
 def tearDown(self):self.t.cleanup()
 def test_unknown_product_rejected(self):
  with self.assertRaises(KeyError):load_product(self.root,"missing")
 @patch("src.keddeh_product_runtime.integrity_readback")
 def test_product_receipt_ledger_outbox(self,readback):
  readback.return_value={"valid":True};r=run_product(self.root,"test.application",True)["receipt"];self.assertEqual(r["promotion_state"],"LOCAL_PASS");self.assertTrue(r["ledger_readback"]);self.assertTrue(Path(r["outbox_handoff"]).exists())
 @patch("src.keddeh_product_runtime.integrity_readback")
 def test_missing_module_fails(self,readback):
  readback.return_value={"valid":True};p=self.root/"config"/"kapp_product_registry.json";r=json.loads(p.read_text());r["products"][0]["modules"]=["src/missing.py"];p.write_text(json.dumps(r));self.assertEqual(run_product(self.root,"test.application",True)["receipt"]["promotion_state"],"LOCAL_FAIL")
 @patch("src.keddeh_product_runtime.integrity_readback")
 @patch("src.keddeh_product_runtime.subprocess.run")
 def test_failed_test_blocks_promotion(self,run,readback):
  readback.return_value={"valid":True};run.return_value.returncode=1;run.return_value.stdout="";run.return_value.stderr="failed";self.assertEqual(run_product(self.root,"test.application",True)["receipt"]["promotion_state"],"LOCAL_FAIL")
if __name__=="__main__":unittest.main()
