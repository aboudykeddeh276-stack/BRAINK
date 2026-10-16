from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "NativeChatBot" / "Sources" / "BRAINKChatBotApp.swift"

def test_primary_surface_is_user_workflow_oriented():
    text = UI.read_text(encoding="utf-8")
    required = [
        "What do you need to get done?",
        "Ask BRAINK",
        "Documents",
        "Files",
        "Legal work",
        "Your work is saved automatically",
    ]
    for token in required:
        assert token in text

def test_internal_operations_are_not_primary_ui_controls():
    text = UI.read_text(encoding="utf-8")
    forbidden_primary = [
        'Button("Load My Data")',
        'Button("Audit Stack")',
        'Button("Learn Files")',
        'Button("Knowledge")',
        'Button("Open Visual")',
        'Button("Project")',
        'Button("Readdress")',
        'Button("Focus")',
        'Button("Close")',
    ]
    for token in forbidden_primary:
        assert token not in text

def test_diagnostics_and_administration_are_separate_surfaces():
    text = UI.read_text(encoding="utf-8")
    assert "struct DiagnosticsPanel: View" in text
    assert "struct AdministrationPanel: View" in text
    assert ".sheet(isPresented: $showDiagnostics)" in text
    assert ".sheet(isPresented: $showAdministration)" in text

def test_status_is_small_and_non_primary():
    text = UI.read_text(encoding="utf-8")
    assert "struct StatusBar: View" in text
    assert ".safeAreaInset(edge: .bottom)" in text
