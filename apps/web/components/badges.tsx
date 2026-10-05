import type { ReactNode } from "react";

function Pill({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <span className={`badge ${className}`}>{children}</span>;
}

/** Real vs synthetic data provenance (docs/10 §2: DataCoverageBadge). */
export function DataCoverageBadge({ synthetic }: { synthetic: boolean }) {
  return synthetic ? (
    <Pill className="border-caution/40 bg-caution/10 text-caution">
      synthetic data
    </Pill>
  ) : (
    <Pill className="border-up/40 bg-up/10 text-up">real data</Pill>
  );
}

export type Confidence = "high" | "moderate" | "low";

/**
 * Crude Phase-1 confidence proxy from relative interval width.
 * Phase 2 replaces this with calibrated coverage (docs/05).
 */
export function confidenceFromBand(
  price: number,
  low: number,
  high: number,
): Confidence {
  if (!price || price <= 0) return "low";
  const relWidth = (high - low) / price;
  if (relWidth < 0.15) return "high";
  if (relWidth < 0.35) return "moderate";
  return "low";
}

export function ConfidenceBadge({ level }: { level: Confidence }) {
  const styles: Record<Confidence, string> = {
    high: "border-up/40 bg-up/10 text-up",
    moderate: "border-info/40 bg-info/10 text-info",
    low: "border-caution/40 bg-caution/10 text-caution",
  };
  return <Pill className={styles[level]}>{level} confidence</Pill>;
}

export function SourceBadge({ source }: { source: string }) {
  return (
    <Pill className="border-terminal-border bg-terminal-bg text-terminal-muted">
      {source === "stored" ? "cached forecast" : "live forecast"}
    </Pill>
  );
}
