import { useEffect, useMemo, useRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useJson } from '@/lib/api';
import type { CapabilityFile, ModelsIndex } from '@/types/data';
import { providerColor } from '@/types/data';

export interface PricePerformancePoint {
  modelId: string;
  name: string;
  provider: string | null;
  price: number;
  outputPrice: number | null;
  score: number;
  benchmarkCount: number;
  sourceCount: number;
  evidenceDate: string | null;
  releaseDate: string | null;
  isCurrent: boolean;
}

/** 只使用有真实公开输入价和编程综合证据的模型；不以 0 或估算值补缺。 */
export function buildPricePerformancePoints(
  index: ModelsIndex,
  coding: CapabilityFile,
): PricePerformancePoint[] {
  if (!coding.composite) return [];

  const modelById = new Map(index.models.map((model) => [model.model_id, model]));
  const latestEvidenceById = new Map<string, string>();
  for (const row of coding.official) {
    const evidence = row.evaluation_date || row.upstream_updated_at;
    if (!evidence) continue;
    const previous = latestEvidenceById.get(row.model_id);
    if (!previous || evidence > previous) {
      latestEvidenceById.set(row.model_id, evidence);
    }
  }

  const points: PricePerformancePoint[] = [];
  for (const composite of coding.composite.models) {
    const model = modelById.get(composite.model_id);
    const price = model?.price_input_usd_per_mtok;
    if (!model || typeof price !== 'number' || !Number.isFinite(price) || price <= 0) continue;
    points.push({
      modelId: composite.model_id,
      name: model.display_name || composite.model_id,
      provider: model.provider ?? null,
      price,
      outputPrice: model.price_output_usd_per_mtok,
      score: composite.index,
      benchmarkCount: composite.benchmark_count,
      sourceCount: composite.source_count,
      evidenceDate: latestEvidenceById.get(composite.model_id) ?? null,
      releaseDate: model.release_date,
      isCurrent: model.is_current === true,
    });
  }
  return points;
}

/**
 * 价格越低、得分越高越优。相同价格先比较最高分；完全重合的模型都保留在前沿。
 */
export function computeParetoFrontier(
  points: readonly PricePerformancePoint[],
): PricePerformancePoint[] {
  const sorted = [...points]
    .filter((point) => Number.isFinite(point.price) && point.price > 0 && Number.isFinite(point.score))
    .sort((a, b) => a.price - b.price || b.score - a.score || a.name.localeCompare(b.name));
  const frontier: PricePerformancePoint[] = [];
  let bestCheaperScore = -Infinity;

  for (let start = 0; start < sorted.length;) {
    let end = start + 1;
    while (end < sorted.length && sorted[end].price === sorted[start].price) end += 1;
    const bestAtPrice = sorted[start].score;
    if (bestAtPrice > bestCheaperScore) {
      frontier.push(...sorted.slice(start, end).filter((point) => point.score === bestAtPrice));
      bestCheaperScore = bestAtPrice;
    }
    start = end;
  }
  return frontier;
}

export function escapeChartHtml(value: unknown): string {
  return String(value ?? '—')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

/** 编程性价比矩阵：输入价格（对数轴）× 编程相对百分位。 */
export function PricePerformanceMatrix({ index }: { index: ModelsIndex | null }) {
  const { data: coding, loading } = useJson<CapabilityFile>('/data/capabilities/coding.json');
  const [showLegacy, setShowLegacy] = useState(false);

  const points = useMemo(
    () => (index && coding ? buildPricePerformancePoints(index, coding) : []),
    [index, coding],
  );
  const current = useMemo(() => points.filter((point) => point.isCurrent), [points]);
  const legacy = useMemo(() => points.filter((point) => !point.isCurrent), [points]);
  const pareto = useMemo(() => computeParetoFrontier(current), [current]);
  const frontierIds = useMemo(() => new Set(pareto.map((point) => point.modelId)), [pareto]);
  const paretoPairs = useMemo(() => {
    const seen = new Set<string>();
    return pareto.reduce<[number, number][]>((pairs, point) => {
      const key = `${point.price}:${point.score}`;
      if (!seen.has(key)) {
        seen.add(key);
        pairs.push([point.price, point.score]);
      }
      return pairs;
    }, []);
  }, [pareto]);

  if (!index || loading) {
    return <section className="panel h-[520px] animate-pulse" aria-label="正在加载编程性价比矩阵" />;
  }

  if (!coding?.composite || current.length < 3) {
    return (
      <section className="panel px-5 py-6">
        <h2 className="text-lg font-bold text-slate-100">编程性价比矩阵</h2>
        <p className="mt-2 text-sm text-slate-500">
          当前模型中有公开价格且同时有编程综合证据的不足 3 个，暂不绘图（不拿 0 分或估算价格填充）。
        </p>
      </section>
    );
  }

  const noPriceCount = coding.composite.models.length - points.length;
  return (
    <section className="panel px-5 py-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-100">编程性价比矩阵</h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
            输入价格（USD/1M tokens，对数轴）与编程相对百分位对比；越靠左上代表越便宜且相对表现越强。
            青色虚线为 <b>Pareto 前沿</b>：不存在价格不高于它、同时得分不低于它的更优替代。
          </p>
        </div>
        <button
          type="button"
          className="badge cursor-pointer select-none disabled:cursor-not-allowed disabled:opacity-40"
          onClick={() => setShowLegacy((value) => !value)}
          disabled={legacy.length === 0}
          aria-pressed={showLegacy}
        >
          {showLegacy ? <EyeOff size={12} aria-hidden /> : <Eye size={12} aria-hidden />}
          {showLegacy ? '隐藏历史模型' : `查看历史分布（${legacy.length}）`}
        </button>
      </div>

      <PriceMatrixChart
        current={current}
        legacy={showLegacy ? legacy : []}
        paretoPairs={paretoPairs}
        frontierIds={frontierIds}
        noPriceCount={noPriceCount}
      />

      <p className="mt-2 text-xs text-slate-500">
        Pareto 前沿（{pareto.length} 个）：{pareto.map((point) => point.name).join(' → ')}
      </p>
    </section>
  );
}

interface ChartMeta {
  name: string;
  provider: string;
  price: number;
  outputPrice: number | null;
  score: number;
  evidenceDate: string | null;
  releaseDate: string | null;
  benchmarkCount: number;
  sourceCount: number;
  isPareto: boolean;
}

function formatPrice(value: number): string {
  return value >= 1 ? value.toFixed(2) : value.toFixed(3);
}

/** ECharts 封装：log X、每个当前点的模型名、Pareto 虚线与可选历史淡化层。 */
function PriceMatrixChart({
  current,
  legacy,
  paretoPairs,
  frontierIds,
  noPriceCount,
}: {
  current: PricePerformancePoint[];
  legacy: PricePerformancePoint[];
  paretoPairs: [number, number][];
  frontierIds: Set<string>;
  noPriceCount: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<import('echarts').ECharts | null>(null);

  useEffect(() => {
    let cancelled = false;
    const onResize = () => chartRef.current?.resize();

    void import('echarts').then((echarts) => {
      if (cancelled || !ref.current) return;
      if (!chartRef.current) {
        chartRef.current = echarts.init(ref.current, undefined, { renderer: 'canvas' });
      }

      const byProvider = new Map<string, PricePerformancePoint[]>();
      for (const point of current) {
        const provider = point.provider ?? '未知厂商';
        byProvider.set(provider, [...(byProvider.get(provider) ?? []), point]);
      }
      const providerNames = [...byProvider.keys()].sort();
      const currentSeries = providerNames.map((provider) => ({
        type: 'scatter' as const,
        name: provider,
        data: (byProvider.get(provider) ?? []).map((point) => {
          const isPareto = frontierIds.has(point.modelId);
          const meta: ChartMeta = {
            name: point.name,
            provider,
            price: point.price,
            outputPrice: point.outputPrice,
            score: point.score,
            evidenceDate: point.evidenceDate,
            releaseDate: point.releaseDate,
            benchmarkCount: point.benchmarkCount,
            sourceCount: point.sourceCount,
            isPareto,
          };
          return {
            value: [point.price, point.score],
            name: point.name,
            meta,
            label: {
              show: true,
              color: isPareto ? '#67e8f9' : '#a8b3c7',
              fontWeight: isPareto ? 700 : 400,
            },
          };
        }),
        symbolSize: (_value: number[], params: { data: { meta: ChartMeta } }) => (
          params.data.meta.isPareto ? 14 : 9
        ),
        itemStyle: {
          color: providerColor(provider === '未知厂商' ? null : provider),
          borderColor: 'rgba(5,9,17,0.75)',
          borderWidth: 1,
        },
        label: {
          position: 'top' as const,
          distance: 7,
          formatter: (params: { data: { meta: ChartMeta } }) => {
            const name = params.data.meta.name;
            return name.length > 24 ? `${name.slice(0, 22)}…` : name;
          },
          fontSize: 10,
        },
        labelLayout: { hideOverlap: true, moveOverlap: 'shiftY' as const },
        emphasis: {
          scale: 1.35,
          label: { show: true, color: '#f8fafc', fontWeight: 700 },
          itemStyle: { shadowBlur: 12, shadowColor: 'rgba(34,211,238,0.45)' },
        },
        z: 10,
      }));

      const option = {
        backgroundColor: 'transparent',
        aria: {
          enabled: true,
          description: `编程性价比矩阵，共 ${current.length} 个当前模型，横轴为对数输入价格，纵轴为编程相对百分位。`,
        },
        grid: { left: 18, right: 28, top: 72, bottom: 12, containLabel: true },
        tooltip: {
          trigger: 'item',
          confine: true,
          backgroundColor: '#0b1424',
          borderColor: 'rgba(34,211,238,0.3)',
          textStyle: { color: '#e2e8f0', fontSize: 12 },
          formatter: (params: { data?: { meta?: ChartMeta } }) => {
            const data = params.data?.meta;
            if (!data) return '';
            const outputPrice = data.outputPrice === null
              ? '—'
              : `$${formatPrice(data.outputPrice)}/1M`;
            return [
              `<b>${escapeChartHtml(data.name)}</b>${data.isPareto ? ' · Pareto' : ''}`,
              `厂商：${escapeChartHtml(data.provider)}`,
              `输入价：$${formatPrice(data.price)}/1M`,
              `输出价：${outputPrice}`,
              `编程相对百分位：${data.score.toFixed(1)}`,
              `证据：${data.benchmarkCount} 个基准 / ${data.sourceCount} 个来源`,
              `发布日期：${escapeChartHtml(data.releaseDate)}`,
              `最近证据日期：${escapeChartHtml(data.evidenceDate)}`,
            ].join('<br/>');
          },
        },
        legend: {
          top: 0,
          type: 'scroll',
          data: [...providerNames, ...(legacy.length ? ['历史模型'] : [])],
          textStyle: { color: '#93a0b8', fontSize: 11 },
          pageTextStyle: { color: '#93a0b8' },
        },
        xAxis: {
          type: 'log',
          logBase: 10,
          name: '输入价格 USD/1M（对数）',
          nameLocation: 'middle',
          nameGap: 30,
          nameTextStyle: { color: '#93a0b8' },
          axisLabel: { color: '#93a0b8', formatter: (value: number) => `$${value}` },
          splitLine: { lineStyle: { color: 'rgba(148,163,196,0.08)' } },
        },
        yAxis: {
          type: 'value',
          name: '编程相对百分位',
          nameTextStyle: { color: '#93a0b8' },
          min: (range: { min: number }) => Math.max(0, Math.floor(range.min - 5)),
          max: (range: { max: number }) => Math.min(100, Math.ceil(range.max + 5)),
          axisLabel: { color: '#93a0b8' },
          splitLine: { lineStyle: { color: 'rgba(148,163,196,0.08)' } },
        },
        series: [
          {
            type: 'line' as const,
            data: paretoPairs,
            silent: true,
            lineStyle: { color: '#22d3ee', width: 1.8, type: 'dashed', opacity: 0.85 },
            symbol: 'none',
            z: 5,
          },
          ...(legacy.length ? [{
            type: 'scatter' as const,
            name: '历史模型',
            data: legacy.map((point) => ({
              value: [point.price, point.score],
              name: point.name,
              meta: {
                name: point.name,
                provider: point.provider ?? '未知厂商',
                price: point.price,
                outputPrice: point.outputPrice,
                score: point.score,
                evidenceDate: point.evidenceDate,
                releaseDate: point.releaseDate,
                benchmarkCount: point.benchmarkCount,
                sourceCount: point.sourceCount,
                isPareto: false,
              } satisfies ChartMeta,
            })),
            symbolSize: 7,
            itemStyle: { color: 'rgba(148,163,196,0.28)' },
            emphasis: { itemStyle: { color: 'rgba(148,163,196,0.65)' } },
            z: 1,
          }] : []),
          ...currentSeries,
        ],
      };

      chartRef.current.setOption(option, true);
      chartRef.current.resize();
      window.addEventListener('resize', onResize);
    });

    return () => {
      cancelled = true;
      window.removeEventListener('resize', onResize);
    };
  }, [current, legacy, paretoPairs, frontierIds]);

  useEffect(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);

  const modelNames = current.map((point) => point.name).join('、');
  return (
    <div>
      <div
        ref={ref}
        className="mt-3 h-[440px] w-full"
        role="img"
        aria-label={`编程性价比矩阵，${current.length} 个当前模型：${modelNames}`}
      />
      <p className="mt-2 text-xs leading-5 text-slate-500">
        每个彩色点都标注模型名；青色大点位于 Pareto 前沿。悬停可核对输入/输出价格、发布日期、最近证据日期和证据数。
        {legacy.length > 0 && ' 灰色小点为手动展开的历史模型，不参与当前 Pareto 计算。'}
        {noPriceCount > 0 && ` 另有 ${noPriceCount} 条编程综合记录因缺少公开输入价未加入图表。`}
      </p>
    </div>
  );
}
