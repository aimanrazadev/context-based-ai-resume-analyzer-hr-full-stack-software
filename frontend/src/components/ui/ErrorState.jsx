export default function ErrorState({ message = "Something went wrong." }) {
  return <div className="ds-error-state" role="alert">{message}</div>;
}
