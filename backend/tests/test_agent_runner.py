"""Run limits and the journey hint. No network."""

from agent_fakes import ScriptedMistral, call, london

from organiser.agent.runner import (
    MAX_ROUNDS,
    RUN_DEADLINE_SECONDS,
    RunFailed,
    feed_packet,
    journey_note,
    run_agent,
)
from organiser.config import Settings


def test_rounds_and_deadline_stay_inside_the_proxy_limit():
    timeout = Settings.model_fields["mistral_timeout_seconds"].default
    assert MAX_ROUNDS <= 5
    assert RUN_DEADLINE_SECONDS + timeout < 100


def test_a_slow_run_stops_before_another_round():
    seen = {"n": 0}

    def monotonic():
        seen["n"] += 1
        return 0.0 if seen["n"] == 1 else 100.0

    fake = ScriptedMistral([call("get_state")], [call("get_state")])
    try:
        run_agent(fake, "ag_test", None, "packet", deadline_seconds=10, monotonic=monotonic)
    except RunFailed as exc:
        assert str(exc) == "The assistant took too long."
    else:
        raise AssertionError("The run should have stopped.")
    assert [kind for kind, *_ in fake.calls] == ["start"]
    assert fake.deleted == ["conv_test"]


def test_journey_note_for_a_commute_and_not_outside_the_house():
    assert journey_note("Train to work tomorrow")
    assert "journey source is not connected" in journey_note("I commute at 7")
    assert journey_note("commute with a guest tomorrow") is None
    assert journey_note("buy milk") is None

    packet = feed_packet(london(2026, 11, 2, 8, 0), "Europe/London", 3, "Train to work tomorrow")
    assert "Trigger: feed" in packet
    assert "Journey:" in packet
