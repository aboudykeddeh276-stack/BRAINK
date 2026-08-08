import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / 'scripts' / 'braink_workflow_orchestrator.py'
SPEC = importlib.util.spec_from_file_location('braink_workflow_orchestrator', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BRAINKWorkflowOrchestratorTests(unittest.TestCase):
    def test_classify_routes_adds_required_followups(self):
        routes, reasoning = MODULE.classify_routes('software that can code using my software and task it to each repo')
        self.assertIn('self_sustained_coder', routes)
        self.assertIn('kex_hyperdrive', routes)
        self.assertIn('proof_packet', routes)
        self.assertIn('stack_audit', routes)
        self.assertIn('self_sustained_coder', reasoning)

    def test_build_plan_prefers_explicit_route(self):
        with patch.dict(os.environ, {}, clear=True):
            plan = MODULE.build_plan('proof packet', 'stack_audit', dict(os.environ))
        self.assertEqual(plan.routes[0], 'stack_audit')
        self.assertEqual(plan.runtime_mode, 'deterministic_local')

    def test_resolve_runtime_uses_complete_auth_mapping(self):
        env = {
            'BRAINK_CHAT_RUNTIME': 'https://braink.example.com/chat',
            'EXPO_PUBLIC_OAUTH_PORTAL_URL': 'https://braink.example.com',
            'EXPO_PUBLIC_OAUTH_SERVER_URL': 'https://braink.example.com/api',
            'EXPO_PUBLIC_APP_ID': 'braink-app',
        }
        mode, endpoint, fallback_reason, auth_ok = MODULE.resolve_runtime(env)
        self.assertEqual(mode, 'bridged_runtime')
        self.assertEqual(endpoint, 'https://braink.example.com/chat')
        self.assertIsNone(fallback_reason)
        self.assertTrue(auth_ok)

    def test_resolve_runtime_falls_back_without_auth(self):
        env = {'BRAINK_CHAT_RUNTIME': 'https://braink.example.com/chat'}
        mode, endpoint, fallback_reason, auth_ok = MODULE.resolve_runtime(env)
        self.assertEqual(mode, 'deterministic_local')
        self.assertEqual(endpoint, '')
        self.assertIn('auth mapping', fallback_reason)
        self.assertFalse(auth_ok)

    def test_smoke_validation_requires_alignment_and_routes(self):
        validation = MODULE.smoke_validation(
            {
                'SMOKE_STATUS': 'DONE',
                'SMOKE_ROUTES': 'user.input,self_sustained_coder,user.input,kex_hyperdrive',
                'SMOKE_AUDIT_ALIGNMENT': '1.0000',
            }
        )
        self.assertTrue(validation['status_done'])
        self.assertTrue(validation['has_self_sustained_coder'])
        self.assertTrue(validation['has_kex_hyperdrive'])
        self.assertEqual(validation['alignment'], 1.0)


if __name__ == '__main__':
    unittest.main()
