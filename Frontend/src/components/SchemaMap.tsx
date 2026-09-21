import {useEffect, useMemo, useState} from "react";
import type {Schema} from "../api.ts";

/* patients sits at the centre, everything else on a ring around it. The join
   graph is close enough to a star that trigonometry beats a layout library. */
const HUBS = ["patients", "encounters"];
const W = 900, H = 620;

export default function SchemaMap() {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [detail, setDetail] = useState<{name: string; body: string} | null>(null);

  useEffect(() => {
    void fetch("/schema").then(r => r.json()).then(setSchema);
  }, []);

  const at = useMemo(() => {
    const pos: Record<string, [number, number]> = {};
    if (!schema) return pos;
    const cx = W / 2, cy = H / 2;
    pos["patients"] = [cx, cy - 34];
    pos["encounters"] = [cx, cy + 34];
    const ring = schema.tables.map(t => t.name).filter(n => !HUBS.includes(n));
    ring.forEach((name, i) => {
      const angle = (i / ring.length) * 2 * Math.PI - Math.PI / 2;
      pos[name] = [cx + Math.cos(angle) * (W / 2 - 90), cy + Math.sin(angle) * (H / 2 - 60)];
    });
    return pos;
  }, [schema]);

  const show = async (name: string) => {
    const data: {table: string; detail: string} = await (await fetch("/schema/" + name)).json();
    setDetail({name, body: data.detail});
  };

  return (
    <main id="schema-view">
      <p className="muted">18 tables. <code>patients</code> is the hub. No foreign keys are
      declared in this database, so every line below is a convention verified by
      counting orphan rows. Click a table for its columns and notes.</p>
      <svg id="map" viewBox={`0 0 ${W} ${H}`}>
        {schema?.edges
          .filter(e => at[e.source] && at[e.target])
          .map((e, i) => (
            <line key={i} x1={at[e.source][0]} y1={at[e.source][1]}
                  x2={at[e.target][0]} y2={at[e.target][1]} />
          ))}
        {schema?.tables.map(t => {
          const [x, y] = at[t.name];
          const w = t.name.length * 6.6 + 16;
          return (
            <g key={t.name} className={"node" + (HUBS.includes(t.name) ? " hub" : "")}
               onClick={() => void show(t.name)}>
              <rect x={x - w / 2} y={y - 11} width={w} height={22} rx={4} />
              <text x={x} y={y + 4} textAnchor="middle">{t.name}</text>
            </g>
          );
        })}
      </svg>
      {detail && (
        <div className="card" id="detail">
          <h2>{detail.name}</h2>
          <pre>{detail.body}</pre>
        </div>
      )}
    </main>
  );
}
