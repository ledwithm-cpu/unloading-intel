import type { Sensitivity } from "../types";

const CONTROLS: { key: keyof Sensitivity; label: string; help: string; min: number; max: number; step: number; unit: string }[] = [
  { key: "near_empty_pct", label: "Count the belt as near-empty below", help: "How much of the belt must be covered before it counts as carrying freight.", min: 5, max: 50, step: 5, unit: "% covered" },
  { key: "min_stop_seconds", label: "List belt stops and gaps lasting at least", help: "Shorter ones still count in the totals; they are just not listed.", min: 5, max: 60, step: 5, unit: "seconds" },
  { key: "min_free_seconds", label: "Flag people free to help another bay after", help: "How long people must be waiting at an idle belt before it is worth a move.", min: 10, max: 90, step: 5, unit: "seconds" },
];

type Props = { value: Sensitivity; defaults: Sensitivity; onChange: (s: Sensitivity) => void };

export default function SensitivityPanel({ value, defaults, onChange }: Props) {
  const changed = (Object.keys(defaults) as (keyof Sensitivity)[]).some((k) => value[k] !== defaults[k]);
  return (
    <details className="sens">
      <summary>Adjust sensitivity{changed ? " (changed)" : ""}</summary>
      <p className="note">These are the site's own settings. Changing them updates the belt bar, the timeline and this list straight away, from the stored data.</p>
      {CONTROLS.map((c) => (
        <label key={c.key} className="sens-row">
          <span className="sens-label">{c.label}<small>{c.help}</small></span>
          <input type="range" min={c.min} max={c.max} step={c.step} value={value[c.key]}
            onChange={(e) => onChange({ ...value, [c.key]: Number(e.target.value) })} />
          <strong>{value[c.key]}{c.unit.startsWith("%") ? "" : " "}{c.unit}</strong>
        </label>
      ))}
      {changed && (
        <p className="banner">The findings above use the standard settings ({defaults.near_empty_pct}%, {defaults.min_stop_seconds} s, {defaults.min_free_seconds} s).{" "}
          <button className="jump" onClick={() => onChange(defaults)}>Reset to standard</button></p>
      )}
    </details>
  );
}
