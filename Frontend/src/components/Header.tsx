export type Tab = "ask" | "schema";

/* Admin lives in its own service on :8001, so that tab is a link out rather
   than a view here. */
export default function Header({tab, onTab}: {tab: Tab; onTab: (t: Tab) => void}) {
  return (
    <header>
      <h1>SQL Harness</h1>
      <nav>
        <button aria-selected={tab === "ask"} onClick={() => onTab("ask")}>Ask</button>
        <button aria-selected={tab === "schema"} onClick={() => onTab("schema")}>Schema</button>
        <button aria-selected={false}
                onClick={() => window.open("http://localhost:8001/", "_blank")}>Admin</button>
      </nav>
    </header>
  );
}
