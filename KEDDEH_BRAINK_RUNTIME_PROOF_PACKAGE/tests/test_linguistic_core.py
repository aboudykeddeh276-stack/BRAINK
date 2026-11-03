import pytest

from braink_runtime.linguistic_core import (
    LEXICON_V1,
    MAX_INPUT_LENGTH,
    LexiconVersion,
    LinguisticCore,
)


@pytest.fixture()
def core():
    return LinguisticCore()


def test_normalize_lowercases_and_strips(core):
    assert core.normalize("   RUN Diagnostics   ") == "run diagnostics"


def test_normalize_collapses_whitespace(core):
    assert core.normalize("run\t\n   the    ledger") == "run the ledger"


def test_normalize_removes_punctuation_but_keeps_hyphens(core):
    assert core.normalize("verify, the: ledger-chain!") == "verify the ledger-chain"


def test_tokenize_returns_tokens(core):
    assert core.tokenize("Run   the LEDGER.") == ["run", "the", "ledger"]


def test_map_intent_run_is_execute(core):
    result = core.map_intent("run diagnostics")
    assert result["intent"] == "EXECUTE"
    assert result["tokens"] == ["run", "diagnostics"]
    assert result["confidence"] > 0.0
    assert result["lexicon_version"] == LEXICON_V1.version


def test_map_intent_stop_is_halt(core):
    assert core.map_intent("stop now")["intent"] == "HALT"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("verify ledger", "VERIFY"),
        ("status please", "STATUS"),
        ("restart runtime", "RESTART"),
    ],
)
def test_map_intent_known_intents(core, text, expected):
    assert core.map_intent(text)["intent"] == expected


def test_map_intent_unknown(core):
    result = core.map_intent("purple elephant")
    assert result["intent"] == "UNKNOWN"
    assert result["confidence"] == 0.0
    assert result["matched"] == []


def test_map_intent_is_deterministic(core):
    assert core.map_intent("Run Diagnostics!") == core.map_intent("run   diagnostics")


def test_validate_token_valid(core):
    assert core.validate_token("execute") is True


def test_validate_token_empty(core):
    assert core.validate_token("") is False


def test_validate_token_whitespace(core):
    assert core.validate_token("two words") is False


def test_validate_token_too_long(core):
    assert core.validate_token("x" * 129) is False
    assert core.validate_token("x" * 128) is True


def test_validate_token_none(core):
    assert core.validate_token(None) is False


def test_none_input_raises(core):
    with pytest.raises(ValueError):
        core.normalize(None)


def test_empty_input_raises(core):
    with pytest.raises(ValueError):
        core.map_intent("   ")


def test_oversized_input_raises(core):
    with pytest.raises(ValueError):
        core.tokenize("a" * (MAX_INPUT_LENGTH + 1))


def test_non_string_input_raises(core):
    with pytest.raises(ValueError):
        core.normalize(12345)


def test_handle_ambiguity_multiple_intents(core):
    result = core.handle_ambiguity(["run", "stop", "verify"])
    assert result["ambiguous"] is True
    assert set(result["candidates"]) == {"EXECUTE", "HALT", "VERIFY"}
    # scores are rounded to 4 decimal places, so allow rounding slack
    assert abs(sum(result["candidates"].values()) - 1.0) < 1e-3


def test_handle_ambiguity_single_intent(core):
    result = core.handle_ambiguity(["run", "execute"])
    assert result["ambiguous"] is False
    assert result["resolved"] == "EXECUTE"


def test_handle_ambiguity_no_known_tokens(core):
    result = core.handle_ambiguity(["banana"])
    assert result["candidates"] == {}
    assert result["resolved"] == "UNKNOWN"


def test_handle_ambiguity_none_raises(core):
    with pytest.raises(ValueError):
        core.handle_ambiguity(None)


def test_lexicon_version(core):
    assert core.lexicon_version() == "lexicon-1.0.0"


def test_custom_lexicon_version():
    lexicon = LexiconVersion(version="lexicon-test", terms={"ping": "STATUS"})
    custom = LinguisticCore(lexicon)
    assert custom.lexicon_version() == "lexicon-test"
    assert custom.map_intent("ping")["intent"] == "STATUS"
    assert lexicon.known_terms() == ["ping"]
