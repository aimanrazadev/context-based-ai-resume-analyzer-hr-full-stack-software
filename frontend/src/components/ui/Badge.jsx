export default function Badge({ children, tone = "neutral", className = "", ...props }) {
  const toneClass = {
    positive: "ds-tone-positive",
    negative: "ds-tone-negative",
    warning: "ds-tone-warning",
    primary: "ds-tone-primary",
    neutral: "ds-tone-neutral",
  }[tone] || "ds-tone-neutral";

  return (
    <span className={`ds-badge ${toneClass} ${className}`.trim()} {...props}>
      {children}
    </span>
  );
}
