import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type {Approval, Decision, Row} from "../api.ts";
import Gate from "./Gate.tsx";
import Rows from "./Rows.tsx";

/* One question and everything the stream produced for it. A turn can run
   several queries, so results and gates are lists, not single values. */
export interface TurnState {
  question: string;
  thinking: string;
  results: Row[][];
  gates: Approval[];
  toolErrors: string[];
  /* Key of the last tool call shown, to drop the replay after a gate. */
  lastTool: string;
  answer: string;
  error: string;
}

export const emptyTurn = (question: string): TurnState =>
  ({question, thinking: "", results: [], gates: [], toolErrors: [], lastTool: "",
    answer: "", error: ""});

export default function Turn({turn, onDecide}: {turn: TurnState; onDecide: (d: Decision[]) => void}) {
  return (
    <section className="turn">
      <p className="q">{turn.question}</p>
      {turn.thinking && (
        <div className="card"><h2>Reasoning</h2><pre className="thinking">{turn.thinking}</pre></div>
      )}
      {turn.gates.map((gate, i) => <Gate key={i} gate={gate} onDecide={onDecide} />)}
      {turn.results.map((rows, i) => (
        <div className="card" key={i}><h2>Result</h2><Rows rows={rows} /></div>
      ))}
      {turn.toolErrors.map((message, i) => (
        <div className="card" key={i}>
          <h2>Tool error</h2>
          <div className="err">{message}</div>
        </div>
      ))}
      {(turn.answer || turn.error) && (
        <div className="card">
          <h2>Answer</h2>
          <div className="answer">
            {turn.error
              ? <span className="err">{turn.error}</span>
              /* The model writes Markdown, and its comparisons are tables.
                 gfm is what turns those pipe tables into real ones. */
              : <Markdown remarkPlugins={[remarkGfm]}>{turn.answer}</Markdown>}
          </div>
        </div>
      )}
    </section>
  );
}
