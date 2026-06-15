interface Props {
  label: string;
  value: string;
  ratio: number;
  detail?: string;
  tone?: "good" | "neutral" | "warn";
}

export default function MetricBar({
  label,
  value,
  ratio,
  detail,
  tone = "good",
}: Props) {
  const bounded = Math.max(0, Math.min(1, ratio));

  return (
    <div className="eval-metric-bar">
      <div className="eval-metric-bar-header">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="eval-metric-track" aria-hidden="true">
        <span
          className={`eval-metric-fill ${tone}`}
          style={{ width: `${bounded * 100}%` }}
        />
      </div>
      {detail && <p>{detail}</p>}
    </div>
  );
}
