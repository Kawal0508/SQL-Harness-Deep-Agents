import type {Row} from "../api.ts";

export default function Rows({rows}: {rows: Row[]}) {
  if (!rows.length) return <p className="muted">No rows.</p>;
  const cols = Object.keys(rows[0]);
  return (
    <table>
      <thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => <tr key={i}>{cols.map(c => <td key={c}>{String(r[c] ?? "")}</td>)}</tr>)}
      </tbody>
    </table>
  );
}
