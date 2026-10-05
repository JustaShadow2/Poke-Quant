"use client";

import {
  ColorType,
  LineStyle,
  createChart,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

export interface ObservedPoint {
  time: string; // YYYY-MM-DD
  value: number;
}

export interface ForecastBand {
  asOf: string; // YYYY-MM-DD (chart "now")
  horizonTime: string; // YYYY-MM-DD at the forecast horizon
  last: number;
  low: number;
  median: number;
  high: number;
}

/**
 * Observed price (area) + a forecast fan (median line with a low/high band that
 * widens from "now" to the horizon). Uncertainty is always shown, never a lone
 * point (docs/10 §1).
 */
export function ForecastChart({
  observed,
  forecast,
}: {
  observed: ObservedPoint[];
  forecast: ForecastBand | null;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart: IChartApi = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8b98a9",
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      },
      grid: {
        vertLines: { color: "rgba(28,36,50,0.5)" },
        horzLines: { color: "rgba(28,36,50,0.5)" },
      },
      rightPriceScale: { borderColor: "#1c2432" },
      timeScale: { borderColor: "#1c2432", rightOffset: 6 },
      crosshair: { mode: 0 },
      handleScale: false,
      handleScroll: false,
    });

    const sorted = [...observed].sort((a, b) => a.time.localeCompare(b.time));
    const up = forecast ? forecast.median >= forecast.last : true;
    const forecastColor = up ? "#22c55e" : "#ef4444";

    const area = chart.addAreaSeries({
      lineColor: "#3b82f6",
      topColor: "rgba(59,130,246,0.28)",
      bottomColor: "rgba(59,130,246,0.02)",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    area.setData(sorted.map((p) => ({ time: p.time as Time, value: p.value })));

    if (forecast && forecast.horizonTime > forecast.asOf) {
      const seg = (to: number) => [
        { time: forecast.asOf as Time, value: forecast.last },
        { time: forecast.horizonTime as Time, value: to },
      ];
      const band = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false };

      const high = chart.addLineSeries({
        color: `${forecastColor}55`,
        lineStyle: LineStyle.Dotted,
        ...band,
      });
      high.setData(seg(forecast.high));

      const low = chart.addLineSeries({
        color: `${forecastColor}55`,
        lineStyle: LineStyle.Dotted,
        ...band,
      });
      low.setData(seg(forecast.low));

      const median = chart.addLineSeries({
        color: forecastColor,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      median.setData(seg(forecast.median));
    }

    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [observed, forecast]);

  return <div ref={containerRef} className="h-[360px] w-full" />;
}
