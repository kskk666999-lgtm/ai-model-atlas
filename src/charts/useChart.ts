import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { useAppTheme } from '@/lib/theme';

export function useChart(
  optionFactory: () => Record<string, unknown>,
  deps: unknown[],
): { ref: React.RefObject<HTMLDivElement> } {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const theme = useAppTheme();

  useEffect(() => {
    if (!ref.current) return;
    if (!chartRef.current) {
      chartRef.current = echarts.init(ref.current, undefined, { renderer: 'canvas' });
    }
    const chart = chartRef.current;
    chart.setOption(optionFactory() as echarts.EChartsOption, true);
    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(ref.current);
    return () => {
      window.removeEventListener('resize', onResize);
      ro.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme, ...deps]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  return { ref };
}

export const CHART_TEXT = '#93a0b8';
export const CHART_AXIS = 'rgba(148,163,196,0.18)';
export const CHART_BG = 'transparent';
