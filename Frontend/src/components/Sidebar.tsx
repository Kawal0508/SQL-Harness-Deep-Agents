import type {Thread} from "../threads.ts";

interface Props {
  threads: Thread[];
  current: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({threads, current, onSelect, onNew, onDelete}: Props) {
  return (
    <aside id="sidebar">
      <button className="go new-chat" onClick={onNew}>New chat</button>
      <ul className="threads">
        {threads.map(thread => (
          <li key={thread.id} className={thread.id === current ? "active" : ""}>
            <button className="pick" onClick={() => onSelect(thread.id)}>{thread.title}</button>
            <button className="drop" title="Delete thread"
                    onClick={() => onDelete(thread.id)}>&times;</button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
