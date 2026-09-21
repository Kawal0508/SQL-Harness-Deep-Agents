import {useEffect, useState} from "react";
import Header from "./components/Header.tsx";
import type {Tab} from "./components/Header.tsx";
import Ask from "./components/Ask.tsx";
import Sidebar from "./components/Sidebar.tsx";
import SchemaMap from "./components/SchemaMap.tsx";
import {loadThreads, newThread, saveThreads, titleFor} from "./threads.ts";
import type {Thread} from "./threads.ts";

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");
  const [threads, setThreads] = useState<Thread[]>(() => {
    const stored = loadThreads();
    return stored.length ? stored : [newThread()];
  });
  const [current, setCurrent] = useState(() => threads[0].id);

  useEffect(() => { saveThreads(threads); }, [threads]);

  const start = () => {
    const thread = newThread();
    setThreads(ts => [thread, ...ts]);
    setCurrent(thread.id);
  };

  // The first question of a thread names it; later ones leave the name alone.
  const name = (question: string) =>
    setThreads(ts => ts.map(t => t.id === current
      ? {...t, title: titleFor(question), updatedAt: Date.now()}
      : t));

  const drop = (id: string) => {
    void fetch(`/history/${id}`, {method: "DELETE"});
    setThreads(ts => {
      const left = ts.filter(t => t.id !== id);
      const next = left.length ? left : [newThread()];
      if (id === current) setCurrent(next[0].id);
      return next;
    });
  };

  return (
    <>
      <Header tab={tab} onTab={setTab} />
      {tab === "ask" ? (
        <div id="workspace">
          <Sidebar threads={threads} current={current}
                   onSelect={setCurrent} onNew={start} onDelete={drop} />
          {/* The key remounts Ask on a switch, so no thread's turns leak
              into another. */}
          <Ask key={current} sessionId={current} onFirstQuestion={name} />
        </div>
      ) : <SchemaMap />}
    </>
  );
}
