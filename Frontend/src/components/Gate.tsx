import {useState} from "react";
import type {Approval, Decision} from "../api.ts";

/* One gate can cover several tool calls. Collect a decision for each, then
   send them together - the runtime rejects a list of the wrong length. */
export default function Gate({gate, onDecide}: {gate: Approval; onDecide: (d: Decision[]) => void}) {
  const actions = gate.action_requests;
  const [queries, setQueries] = useState<string[]>(
    () => actions.map(a => a.args.query ?? JSON.stringify(a.args, null, 2))
  );
  const [labels, setLabels] = useState<string[]>(() => actions.map(() => ""));
  const [decisions, setDecisions] = useState<(Decision | null)[]>(() => actions.map(() => null));

  const allowed = (name: string) =>
    gate.review_configs.find(c => c.action_name === name)?.allowed_decisions
      ?? ["approve", "reject"];

  const settle = (i: number, decision: Decision, label: string) => {
    const next = decisions.map((d, j) => j === i ? decision : d);
    setDecisions(next);
    setLabels(ls => ls.map((l, j) => j === i ? label : l));
    if (next.every((d): d is Decision => d !== null)) onDecide(next as Decision[]);
  };

  const approve = (i: number, action: typeof actions[number]): Decision =>
    // An edited box is an edit even if Approve was the button pressed.
    queries[i].trim() === String(action.args.query ?? "").trim()
      ? {type: "approve"}
      : {type: "edit",
         edited_action: {name: action.name, args: {...action.args, query: queries[i].trim()}}};

  return (
    <div className="card gate">
      {actions.map((action, i) => (
        <div key={i}>
          <h2>Approve {action.name}</h2>
          <textarea value={queries[i]}
                    readOnly={decisions[i] !== null || !allowed(action.name).includes("edit")}
                    onChange={e => setQueries(qs => qs.map((q, j) => j === i ? e.target.value : q))} />
          <div className="acts">
            {decisions[i] ? <span className="muted">{labels[i]}</span> : <>
              <button className="approve"
                      onClick={() => settle(i, approve(i, action), "approved")}>Approve</button>
              <button className="reject" onClick={() => settle(i, {
                type: "reject",
                message: "Reviewer declined this query. Say what you would have run and why; do not retry it.",
              }, "rejected")}>Reject</button>
            </>}
          </div>
        </div>
      ))}
    </div>
  );
}
