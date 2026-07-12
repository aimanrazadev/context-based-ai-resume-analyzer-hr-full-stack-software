import Card from "./Card";

export default function MetricCard({ label, value, hint, children, className = "", ...props }) {
  return (
    <Card className={`ds-metric-card ${className}`.trim()} {...props}>
      <div className="ds-metric-card__label">{label}</div>
      <div className="ds-metric-card__value">{value}</div>
      {hint && <div className="ds-metric-card__hint">{hint}</div>}
      {children}
    </Card>
  );
}
