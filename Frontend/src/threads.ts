/* The thread list lives in the browser.

   The server keys threads by id and LangGraph's checkpointer lists
   checkpoints within a thread, not the threads themselves, so enumerating
   them would mean a second table. The page already knows which ids it
   created. The cost is that the list is per-browser: the threads survive a
   restart, the index does not follow you to another machine. */

const KEY = "sql-harness.threads";

export interface Thread {
  id: string;
  title: string;
  updatedAt: number;
}

export function loadThreads(): Thread[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Thread[]) : [];
  } catch {
    // Private windows and blocked site data both throw here.
    return [];
  }
}

export function saveThreads(threads: Thread[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(threads));
  } catch {
    // A lost thread index is a worse session, not a broken one.
  }
}

export const newThread = (): Thread =>
  ({id: crypto.randomUUID(), title: "New chat", updatedAt: Date.now()});

/* The first question names the thread. */
export const titleFor = (question: string): string =>
  question.length > 48 ? question.slice(0, 48).trimEnd() + "…" : question;
