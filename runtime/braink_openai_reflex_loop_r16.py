from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Any

from openai import OpenAI

REPO_ROOT = Path(os.environ.get('BRAINK_REPO_ROOT', '.')).resolve()
REPORTS = REPO_ROOT / 'reports'
OUT = Path(os.environ.get('BRAINK_R16_RECEIPT', '/mnt/data/BRAINK_R16_OPENAI_REFLEX_RECEIPT.json'))

MODEL = os.environ.get('BRAINK_OPENAI_MODEL', 'gpt-5.6-sol')
MCP_URL = os.environ['BRAINK_MCP_URL']

READ_ONLY_TOOLS = {
    'braink_capabilities',
    'braink_read_receipt',
    'braink_external_probe',
}
MUTATING_TOOLS = {
    'braink_machine_genesis',
    'braink_regenerative_fabric',
    'braink_global_service_fabric',
}


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def load_braink_state() -> dict[str, Any]:
    candidates = [
        REPORTS / 'BRAINK_R15_EXTERNAL_PATH_RECEIPT.json',
        REPORTS / 'BRAINK_R13_TYPED_SERVICE_FABRIC_RECEIPT.json',
        REPORTS / 'braink_live_service_fabric_r12_receipt.json',
        REPORTS / 'braink_global_service_fabric_r11_receipt.json',
        REPORTS / 'architecture-migration-r8.json',
    ]
    state: dict[str, Any] = {
        'storage_contract': 'ENCODED_MEDIUM->ZEROLESS_GEOMETRY->CONTROLLER->LOGICAL_OBJECTS->VFS_RESOLVER',
        'vfs_role': 'RESOLVER_ONLY',
        'receipts': {},
    }
    for path in candidates:
        if path.exists():
            try:
                state['receipts'][path.name] = json.loads(path.read_text())
            except Exception as exc:
                state['receipts'][path.name] = {'status': 'READ_ERROR', 'error': type(exc).__name__}
    state['state_sha256'] = sha256_json(state)
    return state


def make_mcp_tool() -> dict[str, Any]:
    return {
        'type': 'mcp',
        'server_label': 'braink',
        'server_url': MCP_URL,
        'require_approval': {
            **{name: 'never' for name in sorted(READ_ONLY_TOOLS)},
            **{name: 'always' for name in sorted(MUTATING_TOOLS)},
        },
    }


def run_cycle(objective: str) -> dict[str, Any]:
    braink_state = load_braink_state()
    client = OpenAI()

    instructions = '''
You are a callable reasoning/tool substrate inside BRAINK, not the owner of the control loop.
BRAINK state, identity, lineage, proof and persistence remain authoritative outside this model call.
Use BRAINK MCP tools when they provide relevant execution evidence. Do not reinterpret VFS as storage.
Do not promote external DNS, registrar/registry, TLS/CA, WAN, deployment, persistence, or mutation states without direct tool evidence.
For mutating BRAINK tools, request approval through the MCP approval boundary instead of assuming authority.
Return a compact result that states: observations, tool evidence used, proposed BRAINK state delta, unresolved boundaries.
'''.strip()

    response = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=json.dumps({
            'objective': objective,
            'braink_state': braink_state,
            'control_owner': 'BRAINK',
            'cycle': 'BRAINK->OPENAI->BRAINK_MCP->OPENAI->BRAINK',
        }),
        tools=[make_mcp_tool()],
        tool_choice='auto',
        max_tool_calls=12,
        store=False,
    )

    output_items = []
    for item in response.output:
        if hasattr(item, 'model_dump'):
            output_items.append(item.model_dump())
        elif isinstance(item, dict):
            output_items.append(item)
        else:
            output_items.append({'repr': repr(item)})

    receipt = {
        'schema': 'braink.openai-reflex-loop.r16.receipt',
        'control_owner': 'BRAINK',
        'cycle': 'BRAINK->OPENAI->BRAINK_MCP->OPENAI->BRAINK',
        'model': MODEL,
        'mcp_url': MCP_URL,
        'input_state_sha256': braink_state['state_sha256'],
        'response_id': response.id,
        'response_status': response.status,
        'output_text': response.output_text,
        'output_items': output_items,
        'proposed_state_delta_sha256': sha256_json({'text': response.output_text, 'items': output_items}),
        'promotion_gate': 'BRAINK_MUST_VALIDATE_AND_COMMIT_DELTA',
    }
    receipt['receipt_sha256'] = sha256_json(receipt)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('objective')
    args = ap.parse_args()
    print(json.dumps(run_cycle(args.objective), indent=2))
