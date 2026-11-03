import pytest

from braink_runtime.canonical import (
    canonical_bytes,
    canonical_hash,
    canonical_serialize,
    stable_namespace,
)
from braink_runtime.identity import (
    CollisionError,
    IdentityRegistry,
    detect_collision,
    generate_component_id,
    generate_service_id,
    generate_skill_id,
)


def test_canonical_serialize_is_key_order_independent():
    assert canonical_serialize({"b": 1, "a": 2}) == canonical_serialize({"a": 2, "b": 1})


def test_canonical_serialize_has_no_spaces():
    assert canonical_serialize({"a": 1, "b": "x"}) == '{"a":1,"b":"x"}'


def test_canonical_bytes_and_hash_agree():
    obj = {"z": [1, 2, 3], "a": {"k": "v"}}
    assert canonical_bytes(obj) == canonical_serialize(obj).encode("utf-8")
    assert len(canonical_hash(obj)) == 64


def test_canonical_serialize_rejects_none():
    with pytest.raises(ValueError):
        canonical_serialize(None)


def test_stable_namespace():
    assert stable_namespace("braink", "ledger") == "braink:ledger"


def test_component_id_is_deterministic():
    a = generate_component_id("braink", "ledger", "1.0.0")
    b = generate_component_id("braink", "ledger", "1.0.0")
    assert a == b
    assert len(a) == 64


def test_component_id_changes_with_inputs():
    base = generate_component_id("braink", "ledger", "1.0.0")
    assert base != generate_component_id("braink", "ledger", "1.0.1")
    assert base != generate_component_id("braink", "signer", "1.0.0")
    assert base != generate_component_id("other", "ledger", "1.0.0")


def test_component_id_rejects_blank_inputs():
    with pytest.raises(ValueError):
        generate_component_id("braink", "", "1.0.0")
    with pytest.raises(ValueError):
        generate_component_id(None, "ledger", "1.0.0")


def test_skill_id_deterministic_and_distinct():
    a = generate_skill_id("braink", "ledger-verification")
    assert a == generate_skill_id("braink", "ledger-verification")
    assert a != generate_skill_id("braink", "dns-transport")


def test_service_id_includes_endpoint():
    a = generate_service_id("braink", "dns", "8.8.8.8:53")
    assert a != generate_service_id("braink", "dns", "1.1.1.1:53")
    assert a == generate_service_id("braink", "dns", "8.8.8.8:53")


def test_detect_collision_true_and_false():
    a = generate_component_id("braink", "ledger", "1.0.0")
    b = generate_component_id("braink", "ledger", "1.0.0")
    c = generate_component_id("braink", "signer", "1.0.0")
    assert detect_collision(a, b) is True
    assert detect_collision(a, c) is False


def test_detect_collision_rejects_none():
    with pytest.raises(ValueError):
        detect_collision(None, "x")


def test_registry_registers_without_collision():
    registry = IdentityRegistry()
    ledger_id = registry.register_component("braink", "ledger", "1.0.0")
    signer_id = registry.register_component("braink", "signer", "1.0.0")
    assert ledger_id != signer_id
    assert len(registry) == 2
    assert registry.contains(ledger_id)
    assert registry.get(signer_id)["inputs"]["name"] == "signer"


def test_registry_idempotent_for_same_inputs():
    registry = IdentityRegistry()
    registry.register("abc", {"name": "x"})
    registry.register("abc", {"name": "x"})
    assert len(registry) == 1


def test_registry_raises_on_conflicting_registration():
    registry = IdentityRegistry()
    registry.register("abc", {"name": "x"})
    with pytest.raises(CollisionError):
        registry.register("abc", {"name": "y"})


def test_registry_export_structure():
    registry = IdentityRegistry()
    ident = registry.register_component("braink", "runtime", "1.0.0")
    export = registry.export()
    assert export["count"] == 1
    assert ident in export["identities"]
    assert registry.all_identities() == [ident]


def test_registry_rejects_bad_inputs():
    registry = IdentityRegistry()
    with pytest.raises(ValueError):
        registry.register("", {"a": 1})
    with pytest.raises(ValueError):
        registry.register("abc", None)
