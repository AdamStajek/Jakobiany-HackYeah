export default function Numeric({
  label,
  value,
  onChange,
  min = 0,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  min?: number;
}) {
  return (
    <label className="field">
      {label}
      <input
        type="number"
        min={min}
        value={value ?? ""}
        placeholder="Bez wymagania"
        onChange={(e) =>
          onChange(e.target.value === "" ? null : Number(e.target.value))
        }
      />
    </label>
  );
}
