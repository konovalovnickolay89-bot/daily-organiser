"""Set up the Mistral agent from this repo.

    python -m organiser.agent show   Print what goes in Mistral's agent builder. Needs no key.
    python -m organiser.agent sync   Create the agent (no MISTRAL_AGENT_ID yet) or update it.

``sync`` needs MISTRAL_API_KEY in the environment. It sends the instructions,
the function schemas and the settings from ``spec.py``. It reads no house data.
"""

import argparse
import json
import sys

from organiser.agent.mistral import MistralClient, MistralUnavailable
from organiser.agent.spec import FUNCTIONS, agent_definition
from organiser.config import Settings, get_settings

RULE = "-" * 60


def render_console(settings: Settings) -> str:
    body = agent_definition(settings)
    effort = body["completion_args"].get("reasoning_effort", "none")
    lines = [
        "Mistral agent builder: Daily Organiser",
        "",
        f"Model:             {body['model']}",
        "Built-in tools:    Search on. Premium Search, Code and Image off.",
        f"Reasoning effort:  {'High' if effort == 'high' else effort.capitalize()}",
        "Response format:   Text",
        f"Name:              {body['name']}",
        f"Description:       {body['description']}",
        "",
        "Instructions (paste as is):",
        RULE,
        body["instructions"],
        RULE,
        "",
        f"Functions ({len(FUNCTIONS)}). Use Functions > Add once for each block:",
    ]
    for spec in FUNCTIONS:
        lines += [RULE, json.dumps(spec, indent=2)]
    lines.append(RULE)
    return "\n".join(lines)


def sync(settings: Settings) -> int:
    key = settings.mistral_api_key.get_secret_value().strip()
    if not key:
        print("Set MISTRAL_API_KEY first. Nothing was sent.", file=sys.stderr)
        return 2
    client = MistralClient(key, settings.mistral_base_url, settings.mistral_timeout_seconds)
    body = agent_definition(settings)
    try:
        agent_id = settings.mistral_agent_id.strip()
        if agent_id:
            result = client.update_agent(agent_id, body)
            version = result.get("version")
            print(f"Updated agent {agent_id}" + (f" (version {version})." if version is not None else "."))
        else:
            result = client.create_agent(body)
            new_id = result.get("id")
            if not new_id:
                print("Mistral did not return an agent id.", file=sys.stderr)
                return 1
            print(f"Created agent {new_id}.")
            print("Add this line to .env (on the house box, /etc/daily-organiser.env):")
            print(f"MISTRAL_AGENT_ID={new_id}")
    except MistralUnavailable as exc:
        print(f"{exc} Nothing was changed.", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m organiser.agent", description="Set up the Mistral agent.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show", help="Print the agent builder values. Needs no key.")
    commands.add_parser("sync", help="Create or update the agent in Mistral. Needs MISTRAL_API_KEY.")
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "show":
        print(render_console(settings))
        return 0
    return sync(settings)


if __name__ == "__main__":
    raise SystemExit(main())
