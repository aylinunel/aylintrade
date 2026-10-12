export const pct = (value: number | null | undefined, digits = 1): string =>
  value == null || !Number.isFinite(value) ? "—" : `${(value * 100).toFixed(digits)}%`;

export const number = (value: number | null | undefined, digits = 2): string =>
  value == null || !Number.isFinite(value) ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

export const signed = (value: number | null | undefined, digits = 2): string => {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
};

export const date = (value: string | undefined): string => {
  if (!value) return "Awaiting data";
  const parsed = new Date(`${value.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(parsed.valueOf())
    ? value
    : parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
};

export const title = (value: string): string => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
