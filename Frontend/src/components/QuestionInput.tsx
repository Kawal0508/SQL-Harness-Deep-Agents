interface Props {
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export default function QuestionInput({value, disabled, onChange, onSubmit}: Props) {
  return (
    <div className="row composer">
      <input type="text" value={value} autoFocus
             placeholder="How many living patients are in the database?"
             onChange={e => onChange(e.target.value)}
             onKeyDown={e => { if (e.key === "Enter") onSubmit(); }} />
      <button className="go" disabled={disabled} onClick={onSubmit}>Ask</button>
    </div>
  );
}
