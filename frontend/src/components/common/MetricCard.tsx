interface MetricCardProps {
  label: string;
  value: string;
  note?: string;
  id?: string;
  tone?: "default" | "positive" | "warning" | "negative";
}

export function MetricCard({ label, value, note, id, tone = "default" }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card-${tone}`}>
      <span>{label}</span>
      <strong id={id}>{value}</strong>
      {note ? <small>{note}</small> : null}
    </article>
  );
}
