import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { HashRouter } from 'react-router-dom';
import App from '@/App';
import { clearCache } from '@/lib/api';

// 模拟后端生成的静态 JSON
function mockFetch(data: Record<string, unknown>) {
  return vi.fn(async (url: string | URL | Request) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, '');
    const clean = path.replace(/\?.*$/, '');
    if (clean in data) {
      return new Response(JSON.stringify(data[clean]), { status: 200 });
    }
    return new Response('not found', { status: 404 });
  });
}

const meta = {
  generated_at: '2026-08-30T00:00:00Z',
  pipeline_version: '0.1.0',
  demo_mode: false,
  site_name: 'AI 模型天梯',
  counts: { models: 3, unmapped_models: 1, benchmarks: 4, capabilities_active: 2, records: 20, sources_active: 2, history_snapshots: 2 },
  update: { interval_hours: 12, last_success: '2026-08-29T12:00:00Z', failed_sources: [], degraded_sources: [] },
  weight_presets: [{ preset_id: 'general', name: '通用助手', weights: { reasoning: 1 } }],
};

const modelsIndex = {
  generated_at: '2026-08-30T00:00:00Z',
  models: [
    {
      model_id: 'gpt-5.2-high', display_name: 'GPT-5.2 High', provider: 'OpenAI', family: 'gpt-5',
      variant: null, region: 'us', open_weights: false, license: null, modalities: ['text'],
      context_window: 400000, release_date: '2025-12-11', official_model_page: null,
      capability_indices: { reasoning: 95, coding: 90 },
      overall_index: 92.5, overall_rank: 1, overall_benchmark_count: 6, overall_source_count: 2,
      price_input_usd_per_mtok: 1.25, price_output_usd_per_mtok: 10, output_speed_tps: 120,
      latency_seconds: 0.4, benchmark_count: 6, source_count: 2, rank_changes: {},
    },
    {
      model_id: 'glm-5.3', display_name: 'GLM-5.3', provider: 'Zhipu AI', family: 'glm',
      variant: null, region: 'cn', open_weights: true, license: null, modalities: ['text'],
      context_window: 200000, release_date: null, official_model_page: null,
      capability_indices: { reasoning: 88, coding: 85 },
      overall_index: 86.0, overall_rank: 2, overall_benchmark_count: 5, overall_source_count: 2,
      price_input_usd_per_mtok: 0.6, price_output_usd_per_mtok: 2.2, output_speed_tps: 90,
      latency_seconds: 0.5, benchmark_count: 5, source_count: 2, rank_changes: { reasoning: { d7: 2 } },
    },
  ],
};

const capabilityReasoning = {
  capability_id: 'reasoning',
  name: '逻辑推理',
  short: '推理',
  status: 'active',
  description: null,
  generated_at: '2026-08-30T00:00:00Z',
  benchmarks: [{ benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', source_id: 'livebench', higher_is_better: true, score_unit: 'percent', record_count: 2 }],
  official: [
    {
      benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', capability: 'reasoning',
      source_id: 'livebench', source_name: 'LiveBench（官方）', source_level: 'B', source_url: 'https://livebench.ai/',
      model_id: 'gpt-5.2-high', raw_model_name: 'gpt-5.2-2025-12-11-high', model_is_unmapped: false,
      score: 96.2, score_unit: 'percent', higher_is_better: true, rank: 1, tie: false,
      evaluation_date: '2026-06-25', evaluation_target_type: 'base_model', agent_scaffold: null,
      prompt_mode: null, benchmark_version: '2026-06-25', sample_size: 24, notes: 'test',
      fetched_at: '2026-08-30T00:00:00Z', provider: 'OpenAI', region: 'us', open_weights: false,
    },
    {
      benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', capability: 'reasoning',
      source_id: 'livebench', source_name: 'LiveBench（官方）', source_level: 'B', source_url: 'https://livebench.ai/',
      model_id: 'glm-5.3', raw_model_name: 'glm-5.3', model_is_unmapped: false,
      score: 90.1, score_unit: 'percent', higher_is_better: true, rank: 2, tie: false,
      evaluation_date: '2026-06-25', evaluation_target_type: 'base_model', agent_scaffold: null,
      prompt_mode: null, benchmark_version: '2026-06-25', sample_size: 24, notes: 'test',
      fetched_at: '2026-08-30T00:00:00Z', provider: 'Zhipu AI', region: 'cn', open_weights: true,
    },
  ],
  composite: {
    method: 'percentile-weighted（本站计算，非官方榜单）',
    benchmark_count: 1,
    source_count: 1,
    models: [
      { model_id: 'gpt-5.2-high', index: 100.0, rank: 1, tie: false, benchmark_count: 1, source_count: 1, single_source: true, confidence: 'medium', per_benchmark: [{ benchmark_id: 'livebench-reasoning', percentile: 100 }] },
      { model_id: 'glm-5.3', index: 50.0, rank: 2, tie: false, benchmark_count: 1, source_count: 1, single_source: true, confidence: 'medium', per_benchmark: [{ benchmark_id: 'livebench-reasoning', percentile: 50 }] },
    ],
  },
};

describe('前端核心路径', () => {
  beforeEach(() => {
    clearCache();
    window.location.hash = '#/';
    vi.stubGlobal('fetch', mockFetch({
      '/data/meta.json': meta,
      '/data/homepage.json': { generated_at: meta.generated_at, stats: meta.counts, update: meta.update, top3: { reasoning: [{ model_id: 'gpt-5.2-high', display_name: 'GPT-5.2 High', provider: 'OpenAI', index: 100, rank: 1 }] }, movers_7d: [{ model_id: 'glm-5.3', display_name: 'GLM-5.3', provider: 'Zhipu AI', capability: 'reasoning', delta: 2 }], trend_30d: [] },
      '/data/models/index.json': modelsIndex,
      '/data/capabilities/reasoning.json': capabilityReasoning,
      '/data/source-health.json': { generated_at: '', counts: { healthy: 2, degraded: 0, failed: 0, disabled: 3 }, sources: [] },
    }));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('首页正常加载：统计与前三名可见', async () => {
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText('全球 AI 模型能力')).toBeInTheDocument());
    expect((await screen.findAllByText('收录模型')).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getAllByText('GPT-5.2 High').length).toBeGreaterThan(0));
  });

  it('榜单页支持搜索筛选', async () => {
    window.location.hash = '#/leaderboard?cap=reasoning';
    render(<HashRouter><App /></HashRouter>);
    expect(await screen.findAllByText(/LiveBench 逻辑推理/).then((els) => els.length)).toBeGreaterThan(0);
    const input = screen.getByLabelText('搜索模型');
    fireEvent.change(input, { target: { value: 'glm' } });
    await waitFor(() => expect(screen.queryByText('gpt-5.2-2025-12-11-high')).not.toBeInTheDocument());
    expect(screen.getAllByText('glm-5.3').length).toBeGreaterThan(0);
  });

  it('榜单页可切换到综合指数模式', async () => {
    window.location.hash = '#/leaderboard?cap=reasoning';
    render(<HashRouter><App /></HashRouter>);
    const tab = await screen.findByRole('tab', { name: /综合指数/ });
    fireEvent.click(tab);
    expect(await screen.findAllByText('单一来源').then((els) => els.length)).toBeGreaterThan(0);
  });

  it('数据缺失时显示空状态而非模拟数据', async () => {
    clearCache();
    window.location.hash = '#/';
    vi.stubGlobal('fetch', mockFetch({}));
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText(/暂无已验证数据/)).toBeInTheDocument());
  });
});
