from validate_skill import validate


def test_skill_contract_is_valid() -> None:
    assert validate() == []
