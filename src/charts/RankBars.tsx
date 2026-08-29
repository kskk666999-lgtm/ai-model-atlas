
import { CHART_AXIS, CHART_TEXT, useChart } from "./useChart";

export interface BarItem {
  name: string;
  value: number;
  color: string;
  label?: string;
}

/** 排名柱状图（横向）。 */
export function RankBars({ items, height = 380, unit = '' }: { items: BarItem[]; height?: number; unit?: string }) {
  const { ref } = useChart(() => {
    const sorted = [...items].reverse();
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        valueFormatter: (v: unknown) => `${v}${unit}`,
      },
      grid: { left: 8, right: 40, top: 8, bottom: 8, containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { color: CHART_TEXT, fontSize: 11 },
        splitLine: { lineStyle: { color: CHART_AXIS } },
      },
      yAxis: {
        type: 'category',
        data: sorted.map((i) => i.name),
        axisLabel: { color: CHART_TEXT, fontSize: 12, width: 150, overflow: 'truncate' },
        axisLine: { lineStyle: { color: CHART_AXIS } },
      },
      series: [
        {
          type: 'bar',
          data: sorted.map((i) => ({ value: i.value, itemStyle: { color: i.color, borderRadius: [0, 4, 4, 0] } })),
          barMaxWidth: 18,
          label: {
            show: true,
            position: 'right',
            color: CHART_TEXT,
            fontSize: 11,
            formatter: (p: { value: number }) => `${p.value}${unit}`,
          },
        },
      ],
    };
  }, [JSON.stringify(items), unit]);

  return <div ref={ref} style={{ width: '100%', height }} role="img" aria-label="排名柱状图" />;
}
