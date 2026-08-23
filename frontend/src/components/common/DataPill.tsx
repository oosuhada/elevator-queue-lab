import type { ReactNode } from "react";


interface DataPillProps {
  label: string;
  value?: ReactNode;
  tone?: "neutral" | "live" | "warning" | "evidence";
}

export function DataPill({ label, value, tone = "neutral" }: DataPillProps) {
  return (
    <span className={`data-pill data-pill-${tone}`}>
      <span>{label}</span>
      {value !== undefined ? <strong>{value}</strong> : null}
    </span>
  );
}
