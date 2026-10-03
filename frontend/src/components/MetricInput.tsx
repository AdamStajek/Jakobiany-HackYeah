import type { Fact } from "../data/types";
import { useId } from "react";

export function MetricInput({
  attribute,
  value,
  onChange,
}: {
  attribute: Fact["attribute"];
  value: Fact["value"];
  onChange: (value: Fact["value"]) => void;
}) {
  const labelId = useId();
  const helpId = useId();
  const numeric =
    attribute === "steps_count" || /_(cm|m|percent)$/.test(attribute);
  const options =
    attribute === "surface"
      ? ["paved", "asphalt", "gravel", "cobblestone", "ground", "other"]
      : attribute === "smoothness"
        ? [
            "excellent",
            "good",
            "intermediate",
            "bad",
            "very_bad",
            "horrible",
            "very_horrible",
            "impassable",
          ]
        : ["true", "false"];
  return (
    <label className="field">
      <span id={labelId}>Zaobserwowana wartość metryki (opcjonalnie)</span>
      {numeric ? (
        <input
          aria-labelledby={labelId}
          aria-describedby={helpId}
          type="number"
          min={0}
          step={attribute === "steps_count" ? 1 : "any"}
          value={value === null ? "" : String(value)}
          onChange={(event) =>
            onChange(
              event.target.value === "" ? null : Number(event.target.value),
            )
          }
        />
      ) : (
        <select
          aria-labelledby={labelId}
          aria-describedby={helpId}
          value={value === null ? "" : String(value)}
          onChange={(event) => {
            const raw = event.target.value;
            onChange(
              raw === ""
                ? null
                : raw === "true"
                  ? true
                  : raw === "false"
                    ? false
                    : raw,
            );
          }}
        >
          <option value="">Nie podaję wartości</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option === "true" ? "Tak" : option === "false" ? "Nie" : option}
            </option>
          ))}
        </select>
      )}
      <small id={helpId}>
        Wymiary w cm, odległość w m, nachylenie w %. Dodaj zdjęcie, aby
        automatycznie zweryfikować wartość.
      </small>
    </label>
  );
}
