"""Agent service. Read-only, port 8000.

Wraps the agent from `agent.py` in HTTP and streams a turn to the browser as
Server-Sent Events. Adds no capability the terminal agent does not have: the
same two tools, the same read-only connection, the same approval gate.

    cd Backend && uvicorn api:app --reload --port 8000

Serves Frontend/index.html. Reads Database/health.db and Database/knowledge/.

The gate is the reason this is not two plain endpoints. The obvious shape -
/generate hands the SQL to the client, /execute takes it back - lets the client
send back a different query than the one it was shown. Here the client sends a
decision and never a query string; the SQL stays in checkpointed graph state on
the server the whole time, so the substitution has nothing to act on.

Writes live in `admin.py`, which is a separate process with its own connection.
Nothing in this file or in `tools.py` can write to the database.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

import agent
import tools

load_dotenv()

FRONTEND = Path(__file__).resolve().parent.parent / "Frontend"
# The UI is a Vite/React app. `npm --prefix Frontend run build` writes the
# bundle here; in dev, `npm --prefix Frontend run dev` serves it on :5173 and
# proxies the API routes back to this process instead.
DIST = FRONTEND / "dist"
# Conversation state only. Separate file from health.db, which this service
# opens read-only and must never be written by anything but the admin.
THREADS_DB = Path(__file__).resolve().parent.parent / "Database" / "threads.db"

GRAPH = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the checkpointer for the life of the process.

    AsyncSqliteSaver holds one aiosqlite connection, so it is built here
    rather than per request, and the graph is compiled against it once.
    """
    global GRAPH
    THREADS_DB.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(THREADS_DB) as connection:
        saver = AsyncSqliteSaver(connection)
        await saver.setup()
        GRAPH = agent.build_agent(gated=True, checkpointer=saver)
        yield


app = FastAPI(title="Health data agent", lifespan=lifespan)

# The admin UI is served from :8001 and calls back here to refresh the schema
# view after a table changes. Localhost only; needs real origins before this
# is deployed anywhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One graph for the whole service, compiled in the lifespan above. Sessions
# are thread_ids against its shared checkpointer, not separate graphs -
# building one per session would recompile the agent on every question and
# lose the conversation anyway.


class Ask(BaseModel):
    session_id: str
    question: str


class Decide(BaseModel):
    session_id: str
    decisions: list[dict[str, Any]]


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _text(content: Any) -> str:
    """Flatten message content to plain text.

    Providers disagree on the shape. Anthropic usually hands back a string;
    Gemini hands back a list of content blocks, and a reasoning block carries
    no "text" key at all. Sending the raw value to the browser renders
    "[object Object]", so normalise here rather than in the page.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def _rows_from(content: str) -> list[dict] | None:
    """Pull the row JSON back out of a run_sql result.

    `tools.run_sql` returns a report for the model to read, ending in a
    `rows: [...]` line. The browser wants those rows as a table, so parse that
    one line rather than adding a second tool that returns JSON. A refusal or
    a SQL error has no `rows:` line and yields None.
    """
    for line in content.splitlines():
        if line.startswith("rows: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                return None
    return None


async def run(payload: Any, session_id: str) -> AsyncIterator[str]:
    """Stream one leg of a turn: start it, or resume it after a decision.

    Ends either at an approval gate or at the final answer. A single question
    can gate more than once, so the client loops: stream, decide, stream again.
    """
    config = {"configurable": {"thread_id": session_id}}
    try:
        # v1 on purpose, even though agent.py calls invoke with version="v2".
        # The two versions differ in stream shape, not just detail: with a list
        # of stream_modes, v1 yields (mode, payload) tuples and v2 yields
        # {"type", "ns", "data"} dicts, and v2 additionally routes "messages"
        # through the content-block event protocol rather than the
        # (chunk, metadata) pairs handled below. Passing version="v2" here
        # fails with "too many values to unpack (expected 2)".
        async for mode, chunk in GRAPH.astream(
            payload, config=config, stream_mode=["updates", "messages"]
        ):
            if mode == "messages":
                # (token chunk, metadata). Text is the model reasoning out
                # loud; tool-call fragments arrive here too and are skipped,
                # because the whole call shows up in `updates` once complete.
                token = chunk[0]
                if isinstance(token, AIMessage):
                    text = _text(token.content)
                    if text:
                        yield sse("thinking", text)
                continue

            for node in chunk.values():
                if not isinstance(node, dict):
                    continue
                for message in node.get("messages", []):
                    if isinstance(message, AIMessage):
                        for call in message.tool_calls:
                            # The id lets the page drop the duplicate: resuming
                            # after a gate replays the node that made this
                            # call, so the same event arrives on /ask and
                            # again on /decide.
                            yield sse("tool", {
                                "id": call.get("id"),
                                "name": call["name"],
                                "args": call["args"],
                            })
                    elif isinstance(message, ToolMessage):
                        rows = _rows_from(str(message.content))
                        if rows is not None:
                            yield sse("rows", rows)
                        elif message.status == "error":
                            yield sse("tool_error", str(message.content))

        # astream leaves the interrupt in state rather than returning it, so
        # ask the graph what it is waiting on.
        state = await GRAPH.aget_state(config)
        if state.interrupts:
            value = state.interrupts[0].value
            # review_configs carries allowed_decisions per action. The page
            # draws its buttons from that, so a tool whose gate allows only
            # approve/reject never renders an Edit button it cannot use.
            yield sse(
                "approval",
                {
                    "action_requests": value["action_requests"],
                    "review_configs": value.get("review_configs", []),
                },
            )
            return

        # After a rejection the newest message is the rejection ToolMessage,
        # and sending that back as the answer hides what the model actually
        # said. Walk to the newest AIMessage carrying text instead.
        messages = state.values["messages"]
        final = next(
            (
                message
                for message in reversed(messages)
                if isinstance(message, AIMessage) and _text(message.content).strip()
            ),
            messages[-1],
        )
        yield sse("answer", _text(final.content))
    except Exception as exc:  # a failed turn must close the stream, not hang it
        yield sse("error", repr(exc))


@app.post("/ask")
async def ask(body: Ask) -> StreamingResponse:
    payload = {"messages": [{"role": "user", "content": body.question}]}
    return StreamingResponse(
        run(payload, body.session_id), media_type="text/event-stream"
    )


@app.post("/decide")
async def decide(body: Decide) -> StreamingResponse:
    """Resume a gated turn.

    Decisions are passed through as given. The accepted shapes are
    `{"type": "approve"}`, `{"type": "reject", "message": ...}` and
    `{"type": "edit", "edited_action": {"name": ..., "args": {...}}}`.

    Never `respond` for a declined query. It synthesises a successful
    ToolMessage, so the model believes a query ran that never did. `reject`
    produces an error the model has to account for, which is the honest
    outcome.
    """
    payload = Command(resume={"decisions": body.decisions})
    return StreamingResponse(
        run(payload, body.session_id), media_type="text/event-stream"
    )


def _turn(question: str) -> dict:
    """An empty turn in the shape the page renders."""
    return {
        "question": question,
        "thinking": "",
        "results": [],
        "gates": [],
        "toolErrors": [],
        "lastTool": "",
        "answer": "",
        "error": "",
    }


def _turns_from(messages: list, interrupt: dict | None) -> list[dict]:
    """Rebuild the page's turns from stored graph state.

    The live page assembles turns from the event stream. Reopening a thread
    has no stream to replay, so the same shape is derived from the messages
    the checkpointer kept. A message before the first question belongs to no
    turn and is dropped.
    """
    turns: list[dict] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            turns.append(_turn(_text(message.content)))
            continue
        if not turns:
            continue
        turn = turns[-1]
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                args = call["args"]
                argument = args.get("query") or args.get("table") or ""
                turn["thinking"] += "\n[%s] %s\n" % (call["name"], argument)
                # Matches the page's dedupe key, so approving a gate that was
                # left open does not print its call a second time.
                turn["lastTool"] = call.get("id") or ""
            text = _text(message.content)
            if text:
                turn["thinking"] += text
                # The last AI text of a turn is its answer; earlier ones were
                # thinking out loud.
                turn["answer"] = text
        elif isinstance(message, ToolMessage):
            rows = _rows_from(str(message.content))
            if rows is not None:
                turn["results"].append(rows)
            elif message.status == "error":
                turn["toolErrors"].append(str(message.content))
    if interrupt and turns:
        # A thread parked at a gate reopens with that gate still to answer.
        turns[-1]["gates"].append(interrupt)
        turns[-1]["answer"] = ""
    return turns


@app.get("/history/{session_id}")
async def history(session_id: str) -> dict:
    """Replay a stored thread. An unknown id is an empty thread, not a 404."""
    state = await GRAPH.aget_state({"configurable": {"thread_id": session_id}})
    pending = None
    if state.interrupts:
        value = state.interrupts[0].value
        pending = {
            "action_requests": value["action_requests"],
            "review_configs": value.get("review_configs", []),
        }
    return {"turns": _turns_from(state.values.get("messages", []), pending)}


@app.delete("/history/{session_id}")
async def forget(session_id: str) -> dict:
    """Drop a thread's stored state. Deleting an unknown id is a no-op."""
    await GRAPH.checkpointer.adelete_thread(session_id)
    return {"deleted": session_id}


@app.get("/schema")
def schema() -> dict:
    return tools.schema_json()


@app.get("/schema/{table}")
def schema_table(table: str) -> dict:
    text = tools.describe_schema(table)
    if text.startswith("No table named"):
        raise HTTPException(status_code=404, detail=text)
    return {"table": table, "detail": text}


@app.get("/")
def index() -> FileResponse:
    if not (DIST / "index.html").is_file():
        raise HTTPException(
            status_code=503,
            detail="Frontend not built. Run: npm --prefix Frontend run build",
        )
    return FileResponse(DIST / "index.html")


# Mounted last so it cannot shadow an API route. Absent before the first build,
# which /  reports as a 503 rather than failing at import.
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
