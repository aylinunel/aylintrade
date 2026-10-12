import { useMemo, useState } from "react";

import { number } from "../lib/format";

type Series = { name: string; values: number[]; color: string };

const pathFor = (values: number[], width: number, height: number, min: number, max: number): string => {
  if (!values.length) return "";
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
};

export function MultiLineChart({ dates, series }: { dates: string[]; series: Series[] }) {
  const [focus, setFocus] = useState<number | null>(null);
  const width = 820;
  const height = 280;
  const values = series.flatMap((item) => item.values).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const focusedIndex = focus ?? 0;
  const focusDate = focus == null ? null : dates[focusedIndex];

  return (
    <div className="chart-wrap">
      <svg
        className="line-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Normalized cumulative-return comparison. Select benchmark series with the controls above."
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
          setFocus(Math.round(ratio * Math.max(0, dates.length - 1)));
        }}
        onMouseLeave={() => setFocus(null)}
      >
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <line key={ratio} x1="0" x2={width} y1={height * ratio} y2={height * ratio} className="chart-grid" />
        ))}
        {series.map((item) => (
          <path
            key={item.name}
            d={pathFor(item.values, width, height, min, max)}
            className="chart-line"
            style={{ stroke: item.color }}
          />
        ))}
        {focus != null && (
          <>
            <line x1={(focus / Math.max(1, dates.length - 1)) * width} x2={(focus / Math.max(1, dates.length - 1)) * width} y1="0" y2={height} className="chart-focus" />
            {series.map((item) => {
              const value = item.values[focusedIndex];
              const y = height - ((value - min) / (max - min || 1)) * height;
              return <circle key={item.name} cx={(focusedIndex / Math.max(1, dates.length - 1)) * width} cy={y} r="4" style={{ fill: item.color }} />;
            })}
          </>
        )}
      </svg>
      <div className="chart-axis"><span>{dates[0]}</span><span>{dates.at(-1)}</span></div>
      <div className="chart-readout" aria-live="polite">
        {focusDate ? (
          <>
            <strong>{focusDate}</strong>
            {series.map((item) => <span key={item.name}>{item.name}: {number(item.values[focusedIndex], 2)}×</span>)}
          </>
        ) : "Hover to inspect a dated observation. Series controls are keyboard-operable."}
      </div>
    </div>
  );
}

export function Sparkline({ values, color = "var(--atlas)" }: { values: number[]; color?: string }) {
  const points = useMemo(() => values.filter(Number.isFinite), [values]);
  if (points.length < 2) return <span className="spark-empty">No eligible history</span>;
  const min = Math.min(...points);
  const max = Math.max(...points);
  return (
    <svg viewBox="0 0 160 42" className="sparkline" role="img" aria-label="Recent series history">
      <path d={pathFor(points, 160, 38, min, max)} style={{ stroke: color }} />
    </svg>
  );
}
