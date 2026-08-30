import { describe, expect, it } from 'vitest';
import { filterCurrent, joinRows } from '@/components/OfficialTable';
import {
  computeParetoFrontier,
  escapeChartHtml,
  type PricePerformancePoint,
} from '@/components/PricePerformanceMatrix';
import type { ModelIndexItem, OfficialRow } from '@/types/data';

const baseModel: ModelIndexItem = {
  model_id: 'current-model',
  display_name: 'Current Model',
  provider: 'Test',
  family: 'test',
  variant: null,
  region: null,
  open_weights: null,
  license: null,
  modalities: ['text'],
  context_window: null,
  release_date: '2026-01-01',
  official_model_page: null,
  capability_indices: {},
  overall_index: null,
  overall_rank: null,
  overall_benchmark_count: null,
  overall_source_count: null,
  price_input_usd_per_mtok: 1,
  price_output_usd_per_mtok: 2,
  output_speed_tps: null,
  latency_seconds: null,
  benchmark_count: 1,
  source_count: 1,
  is_current: true,
  freshness_bucket: 'ACTIVE',
  rank_changes: {},
};

function row(overrides: Partial<OfficialRow>): OfficialRow {
  return {
    benchmark_id: 'bench',
    benchmark_name: 'Bench',
    capability: 'swe',
    source_id: 'source',
    source_name: 'Source',
    source_level: 'A',
    source_url: 'https://example.com',
    model_id: 'current-model',
    raw_model_name: 'Current Model',
    model_is_unmapped: false,
    score: 80,
    score_unit: 'percent',
    higher_is_better: true,
    rank: 1,
    evaluation_date: '2026-02-01',
    evaluation_target_type: 'model_plus_agent',
    agent_scaffold: 'Agent',
    prompt_mode: null,
    benchmark_version: null,
    sample_size: null,
    fetched_at: '2026-03-01T00:00:00Z',
    ...overrides,
  };
}

function point(modelId: string, price: number, score: number): PricePerformancePoint {
  return {
    modelId,
    name: modelId,
    provider: 'Test',
    price,
    outputPrice: null,
    score,
    benchmarkCount: 2,
    sourceCount: 2,
    evidenceDate: null,
    releaseDate: null,
    isCurrent: true,
  };
}

describe('CURRENT fail-closed filtering', () => {
  it('only admits an explicitly current mapped model', () => {
    const rows = joinRows([
      row({}),
      row({ model_id: 'unknown-mapped-status' }),
      row({
        model_id: 'unmapped--swebench--doubao',
        raw_model_name: 'Doubao-Seed-Code',
        model_is_unmapped: true,
      }),
      row({ model_id: 'record-says-legacy', is_current: false }),
    ], [
      baseModel,
      { ...baseModel, model_id: 'unknown-mapped-status', is_current: undefined },
      { ...baseModel, model_id: 'record-says-legacy', is_current: true },
    ]);

    const { current, legacy } = filterCurrent(rows);
    expect(current.map((item) => item.model_id)).toEqual(['current-model']);
    expect(legacy.map((item) => item.model_id)).toEqual([
      'unknown-mapped-status',
      'unmapped--swebench--doubao',
      'record-says-legacy',
    ]);
  });
});

describe('Pareto frontier', () => {
  it('removes dominated points and handles equal-price points correctly', () => {
    const frontier = computeParetoFrontier([
      point('same-price-low', 1, 80),
      point('cheap-best', 1, 90),
      point('dominated-middle', 2, 85),
      point('frontier-a', 3, 95),
      point('frontier-b', 3, 95),
      point('dominated-expensive', 4, 94),
    ]);

    expect(frontier.map((item) => item.modelId)).toEqual([
      'cheap-best',
      'frontier-a',
      'frontier-b',
    ]);
  });

  it('escapes untrusted tooltip text', () => {
    expect(escapeChartHtml('<img src=x onerror="boom"> & test')).toBe(
      '&lt;img src=x onerror=&quot;boom&quot;&gt; &amp; test',
    );
  });
});
