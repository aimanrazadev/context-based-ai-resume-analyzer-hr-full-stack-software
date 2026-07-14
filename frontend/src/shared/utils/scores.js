export function getScoreTone(score) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));

  if (value >= 75) {
    return {
      name: "positive",
      color: "#16a34a",
      border: "#c7ecd6",
      background: "#f8fffb",
    };
  }

  if (value >= 50) {
    return {
      name: "warning",
      color: "#f59e0b",
      border: "#fde68a",
      background: "#fffbeb",
    };
  }

  return {
    name: "negative",
    color: "#ef4444",
    border: "#fecaca",
    background: "#fff5f5",
  };
}
