export function truncate(value = "", maxLength = 80) {
  if (!value) return "-";
  return value.length > maxLength ? `${value.slice(0, maxLength).trim()}...` : value;
}

export function formatCount(value) {
  return Number(value || 0).toLocaleString();
}
