"""Run the evaluation set against the agent and report measured accuracy.

Each case runs on a fresh thread_id so nothing leaks between questions. The
agent is asked for a single number under a schema, which makes grading exact
rather than a guess at what the prose meant; the SQL it used is captured with
every answer so a pass can be audited by hand.

    python eval.py            run the whole set, print a markdown report
    python eval.py --list     print cases and ground truth, no API calls
    python eval.py --only ID  run one case

Redirect to keep the report: `python eval.py > eval_results.md`
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.callbacks import UsageMetadataCallbackHandler
from pydantic import BaseModel, Field

import agent
import tools
from eval_cases import CASES

CONCURRENCY = int(os.getenv("EVAL_CONCURRENCY", "3"))

# Free API tiers cap requests per minute, and one case spends several of them.
# Without a retry the set reports failures that are quota, not accuracy - a
# first run on Gemini's free tier scored 7/12 where all five "failures" were
# 429s and nothing was answered wrongly. A wrong number here is worse than a
# slow run, so back off and finish.
RATE_LIMIT_RETRIES = 5
DEFAULT_BACKOFF_SECONDS = 30.0


def _is_rate_limit(exc: Exception) -> bool:
    text = repr(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "RateLimit" in text


def _backoff(exc: Exception) -> float:
    """Honour the server's own retryDelay when it sends one."""
    match = re.search(r"retryDelay['\"]?:\s*['\"](\d+(?:\.\d+)?)s", repr(exc))
    return float(match.group(1)) + 2 if match else DEFAULT_BACKOFF_SECONDS

# Claude Opus 5, USD per million tokens. Deep Agents turns prompt caching on by
# default, so cached reads and writes are priced separately - ignoring them
# gives a materially wrong number.
USD_PER_MTOK_IN = 5.00
USD_PER_MTOK_OUT = 25.00
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


class Answer(BaseModel):
    """The single number asked for, and the SQL it came from."""

    answer: float = Field(description="The single number the question asks for.")
    sql: str = Field(description="The exact SQL query that produced the answer.")


def ground_truth(case: dict) -> float:
    """Compute the expected answer from the live database."""
    conn = tools._connect()
    try:
        return float(conn.execute(case["truth_sql"]).fetchone()[0])
    finally:
        conn.close()


def price(usage: dict) -> float:
    """Convert a UsageMetadataCallbackHandler tally into dollars."""
    total = 0.0
    for stats in usage.values():
        details = stats.get("input_token_details") or {}
        cache_read = details.get("cache_read", 0)
        cache_write = details.get("cache_creation", 0)
        # LangChain counts cached tokens inside input_tokens; bill the remainder
        # at full rate and the two cached classes at their own multipliers.
        uncached = max(stats.get("input_tokens", 0) - cache_read - cache_write, 0)
        total += (
            uncached
            + cache_read * CACHE_READ_MULTIPLIER
            + cache_write * CACHE_WRITE_MULTIPLIER
        ) * USD_PER_MTOK_IN / 1e6
        total += stats.get("output_tokens", 0) * USD_PER_MTOK_OUT / 1e6
    return total


def run_case(case: dict) -> dict:
    """Answer one question in an isolated session."""
    usage = UsageMetadataCallbackHandler()
    config = {
        "configurable": {"thread_id": str(uuid4())},  # fresh session per question
        "callbacks": [usage],
    }
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            graph = agent.build_agent(response_format=Answer)
            result = graph.invoke(
                {"messages": [{"role": "user", "content": case["question"]}]},
                config=config,
                version="v2",
            )
            parsed = result.value.get("structured_response")
            return {
                "answer": parsed.answer if parsed else None,
                "sql": (parsed.sql if parsed else "").strip(),
                "cost": price(usage.usage_metadata),
                "error": None if parsed else "no structured_response",
            }
        except Exception as exc:  # one broken run must not sink the whole set
            if attempt < RATE_LIMIT_RETRIES and _is_rate_limit(exc):
                delay = _backoff(exc)
                print(f"  {case['id']}: rate limited, retrying in {delay:.0f}s "
                      f"({attempt + 1}/{RATE_LIMIT_RETRIES})", file=sys.stderr, flush=True)
                time.sleep(delay)
                continue
            return {"answer": None, "sql": "",
                    "cost": price(usage.usage_metadata), "error": repr(exc)}


def graded(got: float | None, want: float) -> bool:
    return got is not None and math.isclose(float(got), want, rel_tol=1e-9)


def main(cases: list[dict]) -> int:
    load_dotenv()
    truths = [ground_truth(c) for c in cases]
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(run_case, cases))

    passed = [graded(r["answer"], t) for r, t in zip(results, truths)]
    cost = sum(r["cost"] for r in results)

    print("# Agent evaluation\n")
    print(f"Harness: Deep Agents, model `{agent.MODEL}`.\n")
    # The rates above are Anthropic's. Against any other provider the token
    # counts are real but the dollar figure is not, so say so rather than
    # printing a number that looks authoritative.
    priced = agent.MODEL.startswith("anthropic:")
    cost_note = f"Measured cost ${cost:.2f}." if priced else (
        f"Cost not priced for `{agent.MODEL}` - the rates in eval.py are Anthropic's."
    )
    print(f"**{sum(passed)} of {len(cases)} correct "
          f"({sum(passed) / len(cases):.0%}).** {cost_note}\n")
    print("| | Case | Expected | Answered |")
    print("|---|---|---|---|")
    for case, truth, result, ok in zip(cases, truths, results, passed):
        got = "error" if result["answer"] is None else f"{result['answer']:,.0f}"
        print(f"| {'PASS' if ok else 'FAIL'} | {case['id']} | {truth:,.0f} | {got} |")

    for case, truth, result, ok in zip(cases, truths, results, passed):
        if ok:
            continue
        print(f"\n## FAIL: {case['id']}\n")
        print(f"- Question: {case['question']}")
        print(f"- Targets: {case['targets']}")
        print(f"- Naive error: {case['naive_error']}")
        print(f"- Expected {truth:,.0f}, answered {result['answer']}")
        if result["error"]:
            print(f"- Error: {result['error']}")
        if result["sql"]:
            print(f"\n```sql\n{result['sql']}\n```")

    print("\nLimitations of this measurement are documented in `eval_cases.py`.")
    return 0 if all(passed) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="print cases, no API calls")
    parser.add_argument("--only", metavar="ID", help="run a single case")
    args = parser.parse_args()

    selected = [c for c in CASES if args.only in (None, c["id"])]
    if not selected:
        sys.exit(f"No case named {args.only!r}. Have: {', '.join(c['id'] for c in CASES)}")

    if args.list:
        for case in selected:
            print(f"{case['id']:<24} {ground_truth(case):>12,.0f}  {case['question']}")
        sys.exit(0)

    sys.exit(main(selected))
