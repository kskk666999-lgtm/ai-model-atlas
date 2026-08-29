
import { CHART_AXIS, CHART_TEXT, useChart } from "./useChart";

export interface SeriesPoint {
  date: string;
  value: number | null;
}

/** 历史趋势折线图（可多系列、可点击关闭）。 */
export function TrendLine({
  series,
  height = 300,
  yName = '',
}: {
  series: { name: string; color: string; points: SeriesPoint[] }[];
  height?: number;
  yName?: string;
}) {
  const { ref } = useChart(() => {
    const dates = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.date)))).sort();
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: {
        top: 0,
        textStyle: { color: CHART_TEXT, fontSize: 12 },
        selected: Object.fromEntries(series.map((s) => [s.name, true])),
      },
      grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { color: CHART_TEXT, fontSize: 11 },
        axisLine: { lineStyle: { color: CHART_AXIS } },
      },
      yAxis: {
        type: 'value',
        name: yName,
        nameTextStyle: { color: CHART_TEXT },
        axisLabel: { color: CHART_TEXT, fontSize: 11 },
        splitLine: { lineStyle: { color: CHART_AXIS } },
        inverse: yName.includes('排名'),
      },
      series: series.map((s) => ({
        name: s.name,
        type: 'line' as const,
        connectNulls: false,
        symbolSize: 5,
        data: dates.map((d) => {
          const p = s.points.find((x) => x.date === d);
          return p && p.value !== null ? p.value : null;
        }),
        itemStyle: { color: s.color },
        lineStyle: { color: s.color, width: 2 },
      })),
    };
  }, [JSON.stringify(series), yName]);

  return <div ref={ref} style={{ width: '100%', height }} role="img" aria-label="历史趋势图" />;
}

/** 价格-能力 / 速度-价格 散点图。 */
export function AbilityScatter({
  points,
  xName,
  yName,
  height = 380,
  logX = false,
}: {
  points: { name: string; x: number; y: number; color: string; modelId: string }[];
  xName: string;
  yName: string;
  height?: number;
  logX?: boolean;
}) {
  const { ref } = useChart(() => ({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (p: { data: { name: string; value: [number, number] } }) =>
        `${p.data.name}<br/>${xName}: ${p.data.value[0]}<br/>${yName}: ${p.data.value[1]}`,
    },
    grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: logX ? 'log' : 'value',
      name: xName,
      nameTextStyle: { color: CHART_TEXT },
      axisLabel: { color: CHART_TEXT, fontSize: 11 },
      splitLine: { lineStyle: { color: CHART_AXIS } },
    },
    yAxis: {
      type: 'value',
      name: yName,
      nameTextStyle: { color: CHART_TEXT },
      axisLabel: { color: CHART_TEXT, fontSize: 11 },
      splitLine: { lineStyle: { color: CHART_AXIS } },
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 10,
        data: points.map((p) => ({
          name: p.name,
          value: [p.x, p.y],
          modelId: p.modelId,
          itemStyle: { color: p.color, opacity: 0.85 },
        })),
      },
    ],
  }), [JSON.stringify(points), xName, yName, logX]);

  return <div ref={ref} style={{ width: '100%', height }} role="img" aria-label="散点图" />;
}
