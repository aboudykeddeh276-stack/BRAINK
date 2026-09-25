import pytest
from runtime.hci.interaction_model import *
from runtime.hci.mcp_router import MCPWorkflowRouter

def test_home_is_user_goal_first():
    home=home_dashboard(ai_state='READY',task_summary={'status':'READY','open_count':3,'attention_count':0},recent_files=[{'name':'a.txt'}],system_summary={'sync':'SYNCED','degraded':False,'diagnostics_available':True})
    labels=[x['label'] for x in home['primary_actions']]
    assert labels==['Ask BRAINK','Browse files','New task','Open tasks']
    assert 'Host diagnostics' not in labels and home['diagnostics']['expanded'] is False

def test_maintenance_cannot_be_primary():
    with pytest.raises(InteractionViolation,match='MAINTENANCE_CANNOT_BE_PRIMARY'):
        InteractionRegistry([InteractionAction('x','x','x',ActionClass.MAINTENANCE,Surface.HOME,Visibility.PRIMARY,'x')],[])

def test_admin_not_primary_home():
    with pytest.raises(InteractionViolation,match='ADMIN_CANNOT_BE_PRIMARY_HOME_ACTION'):
        InteractionRegistry([InteractionAction('x','x','x',ActionClass.ADMIN,Surface.HOME,Visibility.PRIMARY,'x')],[])

def test_destructive_requires_confirmation():
    with pytest.raises(InteractionViolation,match='DESTRUCTIVE_ACTION_REQUIRES_CONFIRMATION'):
        InteractionRegistry([InteractionAction('x','x','x',ActionClass.ADMIN,Surface.ADMIN,Visibility.HIDDEN,'x',True,False)],[])

def test_user_catalog_hides_admin_and_diagnostics():
    ids={x['action_id'] for x in MCPWorkflowRouter().capability_catalog(actor_scope='USER')['entries']}
    assert {'ai.ask','file.open','task.new'}<=ids and 'diag.hosts' not in ids and 'admin.runtime' not in ids

def test_admin_catalog_can_resolve_diagnostics():
    ids={x['action_id'] for x in MCPWorkflowRouter().capability_catalog(actor_scope='ADMIN')['entries']}
    assert 'diag.hosts' in ids and 'admin.runtime' in ids

def test_user_cannot_dispatch_admin():
    with pytest.raises(InteractionViolation,match='PRIVILEGED_ACTION_SCOPE_REQUIRED'):
        MCPWorkflowRouter().dispatch_contract('admin.runtime',{},actor_scope='USER')

def test_user_action_dispatch_is_semantic_not_plumbing():
    d=MCPWorkflowRouter().dispatch_contract('file.open',{'path':'/'},actor_scope='USER')
    assert d['user_intent']=='file.browse' and d['primitive']=='resource' and d['name']=='braink://files'

def test_health_is_secondary_not_primary():
    r=default_registry(); assert r.actions['system.health'].visibility==Visibility.SECONDARY and r.actions['diag.open'].surface==Surface.DIAGNOSTICS
