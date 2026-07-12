export default function LoadingState({ message = "Loading…" }) {
  return <div className="ds-loading-state" role="status">{message}</div>;
}
