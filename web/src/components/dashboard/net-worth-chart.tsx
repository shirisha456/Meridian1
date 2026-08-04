import type { NetWorthSnapshot } from "@/lib/types";

const WIDTH = 640;
const HEIGHT = 160;
const PADDING = 8;

export function NetWorthChart({ snapshots }: { snapshots: NetWorthSnapshot[] }) {
  if (snapshots.length < 2) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Not enough history yet — recompute net worth on a few different days to see a trend.
      </p>
    );
  }

  // Oldest-to-newest for a left-to-right chart, regardless of the caller's sort order.
  const chronological = [...snapshots].sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
  const values = chronological.map((s) => s.net_worth_minor);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = chronological.map((snapshot, index) => {
    const x = PADDING + (index / (chronological.length - 1)) * (WIDTH - PADDING * 2);
    const y = HEIGHT - PADDING - ((snapshot.net_worth_minor - min) / range) * (HEIGHT - PADDING * 2);
    return { x, y };
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const areaPath = `${linePath} L${points[points.length - 1].x},${HEIGHT - PADDING} L${points[0].x},${HEIGHT - PADDING} Z`;

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-40 w-full" preserveAspectRatio="none">
      <line x1={PADDING} y1={HEIGHT - PADDING} x2={WIDTH - PADDING} y2={HEIGHT - PADDING} stroke="var(--border)" strokeWidth={1} />
      <path d={areaPath} fill="var(--primary)" opacity={0.12} />
      <path d={linePath} fill="none" stroke="var(--primary)" strokeWidth={2} />
    </svg>
  );
}
