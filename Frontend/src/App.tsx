import {useState} from "react";
import Header from "./components/Header.tsx";
import type {Tab} from "./components/Header.tsx";
import Ask from "./components/Ask.tsx";
import SchemaMap from "./components/SchemaMap.tsx";

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");
  return (
    <>
      <Header tab={tab} onTab={setTab} />
      {tab === "ask" ? <Ask /> : <SchemaMap />}
    </>
  );
}
