import type { ForecastPoint } from "@/lib/types";

const WIDTH = 640;
const HEIGHT = 160;
const PADDING = 8;

export function ForecastChart({ points }: { points: ForecastPoint[] }) {
  if (points.length < 2) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Not enough data to project a forecast.</p>;
  }

  const values = points.map((p) => p.projected_balance_minor);
  const min = Math.min(...values, 0); // include the zero line so crossing it is visible
  const max = Math.max(...values);
  const range = max - min || 1;

  const chartPoints = points.map((point, index) => {
    const x = PADDING + (index / (points.length - 1)) * (WIDTH - PADDING * 2);
    const y = HEIGHT - PADDING - ((point.projected_balance_minor - min) / range) * (HEIGHT - PADDING * 2);
    return { x, y };
  });

  const linePath = chartPoints.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${chartPoints[chartPoints.length - 1].x},${HEIGHT - PADDING} L${chartPoints[0].x},${HEIGHT - PADDING} Z`;
  const zeroY = HEIGHT - PADDING - ((0 - min) / range) * (HEIGHT - PADDING * 2);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-40 w-full" preserveAspectRatio="none">
      <line x1={PADDING} y1={HEIGHT - PADDING} x2={WIDTH - PADDING} y2={HEIGHT - PADDING} stroke="var(--border)" strokeWidth={1} />
      {min < 0 && (
        <line x1={PADDING} y1={zeroY} x2={WIDTH - PADDING} y2={zeroY} stroke="var(--destructive)" strokeWidth={1} strokeDasharray="4 4" />
      )}
      <path d={areaPath} fill="var(--primary)" opacity={0.12} />
      <path d={linePath} fill="none" stroke="var(--primary)" strokeWidth={2} />
    </svg>
  );
}
