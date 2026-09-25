from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "governance/hci/BRAINK_INTERACTION_CONTRACT_R8.json"
APP = ROOT / "NativeChatBot/Sources/BRAINKChatBotApp.swift"
SHELL = ROOT / "NativeChatBot/Sources/BRAINKWorkspaceShell.swift"


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    standards = {row["id"] for row in contract["standards_basis"]}
    required_standards = {
        "ISO 9241-110:2020",
        "ISO 9241-210:2019",
        "ISO 9241-11:2018",
        "ISO 9241-112:2025",
        "ISO 9241-161:2025",
        "ISO 9241-171:2025",
        "ISO/IEC 25010:2023",
        "ISO/IEC 25019:2023",
    }
    assert required_standards <= standards

    workflows = [row["id"] for row in contract["primary_user_workflows"]]
    assert workflows == ["AI", "TASKS", "FILES"]
    assert contract["visual_interface_contract"]["standard_basis"] == "ISO 9241-161:2025"
    assert contract["accessibility_contract"]["standard_basis"] == "ISO 9241-171:2025"

    forbidden = set(contract["home_contract"]["forbidden"])
    assert {
        "raw_rpc_controls_on_home",
        "model_mount_controls_on_home",
        "vfs_mount_controls_on_home",
        "node_restart_controls_on_home",
        "ledger_raw_view_on_home",
        "maintenance_buttons_in_primary_action_row",
    } <= forbidden

    app = APP.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")

    assert "BRAINKWorkspaceShell()" in app
    assert 'Button("Load My Data")' not in app
    assert 'Button("Audit Stack")' not in app
    assert 'Button("Learn Files")' not in app
    assert 'Button("Knowledge")' not in app

    assert "accessibilityLabel" in shell
    assert 'Button("Browse Files")' in shell

    for expected in [
        'title: "Ask BRAINK"',
        'title: "Tasks"',
        'title: "Files"',
        'case diagnostics = "Diagnostics"',
        'Text("Details in Diagnostics")',
    ]:
        assert expected in shell, expected

    home_segment = shell.split("struct BRAINKHomeView", 1)[1].split("struct BRAINKTasksView", 1)[0]
    for plumbing in ["RPC", "Mount VFS", "Restart Node", "Ledger Root", "Model Path"]:
        assert plumbing not in home_segment, f"plumbing leaked into Home: {plumbing}"

    assert contract["certification_claim"] == "NONE"
    print("R8_HCI_INTERACTION_CONTRACT_PASS")


if __name__ == "__main__":
    main()
