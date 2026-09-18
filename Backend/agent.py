"""Terminal question-answering agent over the synthetic health database.

Built on Deep Agents (LangChain AI, MIT). The agent gets exactly two tools,
`run_sql` and `describe_schema` from `tools.py`, and `instructions.md` as its
system prompt. Deep Agents' own filesystem, shell and sub-agent tools are
stripped - see `_strip_builtin_tools`.

    python agent.py                interactive loop, queries run unattended
    python agent.py --approve      ask y/n before every query that reads records
    python agent.py --check-tools  assert the tool surface, no API key needed

The model is `HARNESS_MODEL` in .env, defaulting to anthropic:claude-opus-5.
It must carry a `<provider>:` prefix; see the note on MODEL below for what
breaks without one. Whichever provider it names needs that provider's key in
.env - ANTHROPIC_API_KEY, or GOOGLE_API_KEY for google_genai.

A key is required for real work. Deep Agents reaches a provider through its
langchain integration, and none of them can reuse a Claude Code or
subscription login.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import tools

# Before MODEL is read below: HARNESS_MODEL and the provider key both live
# in .env, and every entry point needs them, not just main().
load_dotenv()

# The provider prefix is load-bearing, twice over.
#
# First, Deep Agents looks the harness profile up by the exact model spec and
# returns an EMPTY profile on a miss without falling back to the provider key
# (harness_profiles.py, _harness_profile_for_model). A bare "claude-opus-5"
# therefore silently keeps every built-in tool. Verified: bare string resolves
# 0 exclusions, the prefixed form resolves 8.
#
# Second, the profile below is registered under whatever provider MODEL names.
# Hardcoding "anthropic" here and then pointing MODEL at another provider
# would restore all 8 tools just as silently. `--check-tools` catches both.
MODEL = os.getenv("HARNESS_MODEL", "anthropic:claude-opus-5")
if ":" not in MODEL:
    sys.exit(
        f"HARNESS_MODEL must be '<provider>:<model>', got {MODEL!r}. "
        "Without the prefix no harness profile resolves and the built-in "
        "filesystem and shell tools stay enabled."
    )
PROVIDER = MODEL.split(":", 1)[0]
ROOT = Path(__file__).resolve().parent.parent
INSTRUCTIONS = Path(__file__).resolve().parent / "instructions.md"
# Agreed cohort rules and bands. Small and needed on every question, so it
# rides in the prompt. Per-table notes are the opposite - 18 files, most of
# them irrelevant to any one question - so those load on demand through
# describe_schema instead.
DEFINITIONS = ROOT / "Database" / "knowledge" / "definitions.md"

# Deep Agents ships these and `tools=` is purely additive - it never removes
# them. `excluded_middleware` cannot drop FilesystemMiddleware or
# SubAgentMiddleware either; both are required middleware and excluding them
# raises. The harness profile registry is the supported route.
BUILTIN_TOOLS = frozenset(
    {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep", "execute"}
)

# Only run_sql returns patient records, so only run_sql is worth a reviewer's
# time; describe_schema returns table and column structure.
GATED_TOOLS = {"run_sql"}

OUR_TOOLS = [tools.run_sql, tools.describe_schema]


def _strip_builtin_tools() -> None:
    """Remove Deep Agents' built-in filesystem, shell and sub-agent tools.

    The registry is global and additive, so this runs once at import. A
    misspelled name here silently does nothing, which is why `check_tools`
    asserts the resulting surface rather than trusting the call.
    """
    register_harness_profile(
        PROVIDER,
        HarnessProfile(
            excluded_tools=BUILTIN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )


_strip_builtin_tools()


def system_prompt() -> str:
    parts = [INSTRUCTIONS.read_text(encoding="utf-8")]
    if DEFINITIONS.is_file():
        parts.append(DEFINITIONS.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def build_agent(gated: bool = False, response_format: type | None = None):
    """Compile the agent. `gated` turns on the y/n approval interrupt."""
    return create_deep_agent(
        model=MODEL,
        tools=OUR_TOOLS,
        system_prompt=system_prompt(),
        # A checkpointer is mandatory for interrupts: pause and resume work by
        # persisting graph state. Harmless when ungated.
        checkpointer=InMemorySaver(),
        # "edit" lets a reviewer correct the SQL instead of only accepting or
        # refusing it, and the web UI draws its buttons from this list. A
        # decision whose type is not listed here raises at resume time, so the
        # list and the UI have to agree.
        #
        # "respond" is deliberately absent. It synthesises a SUCCESSFUL tool
        # message, so the model would believe a query ran that never did.
        interrupt_on=(
            {
                name: {"allowed_decisions": ["approve", "edit", "reject"]}
                for name in GATED_TOOLS
            }
            if gated
            else None
        ),
        response_format=response_format,
    )


def decide(action: dict) -> dict:
    """Ask the operator to approve one proposed tool call."""
    print(f"\n  proposed {action['name']}:")
    print(f"    {action['args'].get('query', action['args'])}")
    if input("  run it? [y/N] ").strip().lower() in {"y", "yes"}:
        return {"type": "approve"}
    # "reject" becomes a ToolMessage(status="error") the model must answer for.
    # Never use "respond" to decline - it reports success and the model will
    # believe the query ran.
    return {
        "type": "reject",
        "message": "Reviewer declined this query. Say what you would have run "
        "and why; do not retry it.",
    }


def turn(agent, question: str, config: dict, gated: bool) -> None:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config=config,
        version="v2",
    )
    # while, not if: resuming can hit a second gate in the same turn.
    while result.interrupts:
        decisions = [decide(a) for a in result.interrupts[0].value["action_requests"]]
        result = agent.invoke(
            Command(resume={"decisions": decisions}),
            config=config,  # same thread_id, mandatory
            version="v2",
        )

    messages = result.value["messages"]
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if gated and call["name"] in GATED_TOOLS:
                    continue  # the approval prompt showed this query already
                args = call["args"]
                print(f"  [{call['name']}] {args.get('query') or args.get('table', '')}")
    print(messages[-1].content)


def check_tools() -> None:
    """Assert the model is offered exactly our two tools. No API key needed.

    Two failure modes are real and both are silent, so both are checked:

    1. The profile does not resolve for MODEL, so nothing is excluded at all.
    2. A name in BUILTIN_TOOLS is misspelled or a new built-in ships, so one
       survives the filter.

    The executor keeps every tool registered on purpose - `_ToolExclusionMiddleware`
    filters `request.tools` in `wrap_model_call`, so the ToolNode is not the
    layer to assert on. Here we take what the executor registered and subtract
    what the filter removes; anything left over is what the model is offered.
    """
    from deepagents.profiles.harness.harness_profiles import _get_harness_profile

    # Construction, not a call. ChatGoogleGenerativeAI validates that a key
    # exists in __init__, where ChatAnthropic defers it to request time, so
    # without this the check stops being runnable offline on Gemini. Nothing
    # below reaches the network, and a real key in the environment wins.
    os.environ.setdefault("GOOGLE_API_KEY", "placeholder-no-request-is-made")

    expected = {"run_sql", "describe_schema"}

    profile = _get_harness_profile(MODEL)
    assert profile is not None, (
        f"No harness profile resolves for {MODEL!r}, so nothing is excluded. "
        f"A bare model name misses the provider key - use '{PROVIDER}:<model>'."
    )
    assert profile.excluded_tools == BUILTIN_TOOLS, sorted(profile.excluded_tools)
    assert profile.general_purpose_subagent.enabled is False

    for gated in (False, True):
        registered = set(build_agent(gated=gated).nodes["tools"].bound._tools_by_name)
        assert "task" not in registered, "sub-agent spawning is still enabled"
        offered = registered - BUILTIN_TOOLS
        assert offered == expected, (
            f"gated={gated}: model is offered {sorted(offered)}, expected {sorted(expected)}"
        )
    print(f"tool surface ok: {sorted(expected)} (excluded {len(BUILTIN_TOOLS)} built-ins, no task)")


def main(gated: bool = False) -> None:
    agent = build_agent(gated=gated)
    # One thread_id for the whole session gives conversation memory, so each
    # turn sends only the new message.
    config = {"configurable": {"thread_id": str(uuid4())}}
    print("Ask a question about the health database. 'exit' to quit.")
    print("Every query needs your y/n.\n" if gated else "")
    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        turn(agent, question, config, gated)
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve", action="store_true", help="ask y/n before each query")
    parser.add_argument("--check-tools", action="store_true", help="assert tool surface, no API")
    args = parser.parse_args()

    if args.check_tools:
        check_tools()
        sys.exit(0)
    main(gated=args.approve)
