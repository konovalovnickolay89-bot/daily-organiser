"""The repo is the source of truth for Mistral's agent builder."""

from organiser.agent.__main__ import main
from organiser.agent.functions import HANDLERS
from organiser.agent.spec import FUNCTIONS, agent_definition, instructions
from organiser.config import Settings
from organiser.domain import AgentTrigger


def test_every_function_has_a_handler_and_every_handler_a_schema():
    assert [spec["name"] for spec in FUNCTIONS] == list(HANDLERS)


def test_function_schemas_are_closed_and_consistent():
    for spec in FUNCTIONS:
        assert spec["description"], spec["name"]
        parameters = spec["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert set(parameters.get("required", [])) <= set(parameters["properties"]), spec["name"]


def test_change_fields_match_the_allowlist():
    from organiser.agent.functions import ALLOWED_FIELDS

    propose = next(spec for spec in FUNCTIONS if spec["name"] == "propose_change")
    changes = propose["parameters"]["properties"]["changes"]
    assert changes["additionalProperties"] is False
    assert set(changes["properties"]) == set().union(*ALLOWED_FIELDS.values())
    assert "owner" not in changes["properties"]
    assert set(propose["parameters"]["properties"]["action"]["enum"]) == set(ALLOWED_FIELDS)


def test_instructions_name_every_function_and_trigger():
    text = instructions(Settings())
    for spec in FUNCTIONS:
        assert spec["name"] in text
    for trigger in AgentTrigger:
        assert trigger.value in text
    assert "Europe/London" in text
    assert "Not for the house log." in text
    assert "No greeting" in text


def test_agent_definition_has_search_five_functions_and_high_reasoning():
    body = agent_definition(Settings())
    assert body["model"] == "mistral-medium-latest"
    assert body["name"] == "Daily Organiser"
    assert {"type": "web_search"} in body["tools"]
    kinds = {tool["type"] for tool in body["tools"]}
    assert kinds == {"web_search", "function"}
    names = [tool["function"]["name"] for tool in body["tools"] if tool["type"] == "function"]
    assert names == [spec["name"] for spec in FUNCTIONS]
    assert body["completion_args"] == {"temperature": 0.2, "reasoning_effort": "high"}


def test_reasoning_effort_can_be_left_to_the_model():
    body = agent_definition(Settings(mistral_reasoning_effort=""))
    assert "reasoning_effort" not in body["completion_args"]


def test_show_prints_the_console_values(capsys):
    assert main(["show"]) == 0
    out = capsys.readouterr().out
    assert "Search on. Premium Search, Code and Image off." in out
    assert "Reasoning effort:  High" in out
    assert "Response format:   Text" in out
    for spec in FUNCTIONS:
        assert f'"name": "{spec["name"]}"' in out


def test_sync_without_a_key_sends_nothing(capsys):
    assert main(["sync"]) == 2
    assert "Set MISTRAL_API_KEY first. Nothing was sent." in capsys.readouterr().err
