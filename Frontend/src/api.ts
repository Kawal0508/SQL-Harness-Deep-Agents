/* Shapes of what Backend/api.py sends. They mirror `sse(...)` calls in
   `run()` there; nothing validates them at runtime, so a backend rename shows
   up as a type error here only after this file is updated to match. */

export type Row = Record<string, unknown>;

export interface ToolCall {
  /* Absent on providers that do not id their tool calls; the page then keeps
     every event rather than risk dropping a real one. */
  id?: string | null;
  name: string;
  args: {query?: string; table?: string; [key: string]: unknown};
}

export interface ActionRequest {
  name: string;
  args: {query?: string; [key: string]: unknown};
}

export interface ReviewConfig {
  action_name: string;
  allowed_decisions?: string[];
}

export interface Approval {
  action_requests: ActionRequest[];
  review_configs: ReviewConfig[];
}

export type AgentEvent =
  | {event: "thinking"; data: string}
  | {event: "tool"; data: ToolCall}
  | {event: "rows"; data: Row[]}
  | {event: "approval"; data: Approval}
  | {event: "answer"; data: string}
  | {event: "tool_error"; data: string}
  | {event: "error"; data: string};

/* The three decision shapes the runtime accepts. `respond` is deliberately
   absent: it synthesises a successful ToolMessage for a query that never ran. */
export type Decision =
  | {type: "approve"}
  | {type: "reject"; message: string}
  | {type: "edit"; edited_action: {name: string; args: Record<string, unknown>}};

export interface Column {
  name: string;
  type: string;
}

export interface SchemaTable {
  name: string;
  rows: number;
  summary: string;
  columns: Column[];
}

export interface SchemaEdge {
  source: string;
  column: string;
  target: string;
}

export interface Schema {
  tables: SchemaTable[];
  edges: SchemaEdge[];
}

/* SSE over POST. EventSource is GET-only, so read the response body and split
   frames by hand. */
export async function stream(
  path: string,
  body: unknown,
  on: (event: AgentEvent) => void,
): Promise<void> {
  const res = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!res.body) throw new Error(`${path} returned no body`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, {stream: true});
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = /^event: (.+)$/m.exec(frame);
      const data = /^data: ([\s\S]+)$/m.exec(frame);
      // The one unchecked cast in the app: parsed JSON off the wire, asserted
      // to match the union above.
      if (event && data) on({event: event[1], data: JSON.parse(data[1])} as AgentEvent);
    }
  }
}
