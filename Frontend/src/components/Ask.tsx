import {useEffect, useState} from "react";
import {stream} from "../api.ts";
import type {AgentEvent, Decision} from "../api.ts";
import QuestionInput from "./QuestionInput.tsx";
import Turn, {emptyTurn} from "./Turn.tsx";
import type {TurnState} from "./Turn.tsx";

/* The graph threads turns server-side on session_id, so the page keeps one id
   for its lifetime and just appends a block per question. */
const SESSION = crypto.randomUUID();

export default function Ask() {
  const [turns, setTurns] = useState<TurnState[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.querySelector(".turn:last-of-type")
      ?.scrollIntoView({behavior: "smooth", block: "start"});
  }, [turns.length]);

  // Only the newest turn is ever live: the input stays disabled until its
  // answer arrives, so every event belongs to the last block.
  const patch = (fn: (turn: TurnState) => TurnState) =>
    setTurns(ts => ts.map((t, i) => i === ts.length - 1 ? fn(t) : t));

  const handle = (e: AgentEvent) => {
    switch (e.event) {
      case "thinking":
        return patch(t => ({...t, thinking: t.thinking + e.data}));
      case "tool": {
        // Resuming after a gate replays the call that hit it, so the same
        // event arrives on /ask and again on /decide. Providers that id their
        // calls give an exact key; the rest fall back to the call itself.
        const key = e.data.id ?? `${e.data.name}:${JSON.stringify(e.data.args)}`;
        const line = `\n[${e.data.name}] ${e.data.args.query ?? e.data.args.table ?? ""}\n`;
        return patch(t => t.lastTool === key ? t : {
          ...t,
          thinking: t.thinking + line,
          lastTool: key,
        });
      }
      case "rows":
        return patch(t => ({...t, results: [...t.results, e.data]}));
      case "approval":
        return patch(t => ({...t, gates: [...t.gates, e.data]}));
      case "answer":
        patch(t => ({...t, answer: e.data}));
        return setBusy(false);
      case "tool_error":
        // A rejected or failed query, not the end of the turn: the model still
        // gets to answer for it, so this is a note on the turn, not the answer.
        return patch(t => ({...t, toolErrors: [...t.toolErrors, e.data]}));
      case "error":
        patch(t => ({...t, error: e.data}));
        return setBusy(false);
    }
  };

  const ask = () => {
    const q = question.trim();
    if (!q || busy) return;
    setTurns(ts => [...ts, emptyTurn(q)]);
    setQuestion("");
    setBusy(true);
    void stream("/ask", {session_id: SESSION, question: q}, handle);
  };

  const decide = (decisions: Decision[]) =>
    void stream("/decide", {session_id: SESSION, decisions}, handle);

  return (
    <main>
      {turns.map((turn, i) => <Turn key={i} turn={turn} onDecide={decide} />)}
      <QuestionInput value={question} disabled={busy}
                     onChange={setQuestion} onSubmit={ask} />
    </main>
  );
}
