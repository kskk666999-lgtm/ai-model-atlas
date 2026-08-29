
import { CHART_AXIS, CHART_TEXT, useChart } from "./useChart";

export interface RadarSeries {
  name: string;
  color: string;
  values: (number | null)[]; // 与 indicators 一一对应，缺失为 null
}

/** 能力雷达图（缺失能力用 null 断开，不当作 0 分）。 */
export function ModelRadar({
  indicators,
  series,
  height = 360,
}: {
  indicators: { name: string; max: number }[];
  series: RadarSeries[];
  height?: number;
}) {
  const { ref } = useChart(() => {
    const max = Math.max(100, ...indicators.map((i) => i.max));
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'item' },
      legend: {
        bottom: 0,
        textStyle: { color: CHART_TEXT, fontSize: 12 },
        itemWidth: 14,
        itemHeight: 8,
      },
      radar: {
        indicator: indicators.map((i) => ({ name: i.name, max })),
        splitArea: {
          areaStyle: { color: ['rgba(148,163,196,0.02)', 'rgba(148,163,196,0.05)'] },
        },
        axisLine: { lineStyle: { color: CHART_AXIS } },
        splitLine: { lineStyle: { color: CHART_AXIS } },
        axisName: { color: CHART_TEXT, fontSize: 12 },
        radius: '62%',
        center: ['50%', '46%'],
      },
      series: [
        {
          type: 'radar',
          symbolSize: 4,
          data: series.map((s) => ({
            name: s.name,
            value: s.values,
            itemStyle: { color: s.color },
            lineStyle: { color: s.color, width: 2 },
            areaStyle: { color: s.color, opacity: 0.12 },
            connectNulls: false,
          })),
        },
      ],
    };
  }, [JSON.stringify(indicators), JSON.stringify(series)]);

  return <div ref={ref} style={{ width: '100%', height }} role="img" aria-label="模型能力雷达图" />;
}
