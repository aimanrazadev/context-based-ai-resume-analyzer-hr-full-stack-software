export function SkeletonBlock({ className = "", rounded = true, ...props }) {
  return (
    <div
      className={`ds-skeleton-block ${rounded ? "is-rounded" : ""} ${className}`.trim()}
      aria-hidden="true"
      {...props}
    />
  );
}

export function SkeletonText({ lines = 1, className = "" }) {
  return (
    <div className={`ds-skeleton-text ${className}`.trim()} aria-hidden="true">
      {Array.from({ length: lines }).map((_, index) => (
        <span key={index} className="ds-skeleton-line" />
      ))}
    </div>
  );
}

export default function Skeleton({ className = "" }) {
  return <SkeletonBlock className={className} />;
}
