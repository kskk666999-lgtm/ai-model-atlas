import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { HashRouter } from 'react-router-dom';
import App from '@/App';
import { clearCache } from '@/lib/api';

// 模拟后端生成的静态 JSON
function mockFetch(data: Record<string, unknown>) {
  return vi.fn(async (url: string | URL | Request) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, '');
    const clean = path.replace(/\?.*$/, '').split('#')[0];
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
  latest_commit: 'abc1234',
  counts: { models: 3, unmapped_models: 1, benchmarks: 4, capabilities_active: 2, records: 20, sources_active: 2, history_snapshots: 2 },
  update: { interval_hours: 12, last_success: '2026-08-29T12:00:00Z', failed_sources: [], degraded_sources: [] },
  weight_presets: [{ preset_id: 'general', name: '通用助手', weights: { reasoning: 1 } }],
};

const capabilitiesIndex = {
  generated_at: '2026-08-30T00:00:00Z',
  groups: [
    { group_id: 'text_reasoning', name: '文本与推理' },
    { group_id: 'coding_agent', name: '编程与 Agent' },
  ],
  capabilities: [
    { capability_id: 'reasoning', name: '逻辑推理', short: '推理', group: 'text_reasoning', status: 'active', benchmark_count: 1, has_composite: false },
    { capability_id: 'coding', name: '编程能力', short: '编程', group: 'coding_agent', status: 'active', benchmark_count: 1, has_composite: true },
    { capability_id: 'swe', name: '软件工程（模型 + Agent 系统）', short: '软件工程', group: 'coding_agent', status: 'active', benchmark_count: 1, has_composite: false },
    { capability_id: 'chat_preference', name: '人类偏好与聊天体验', short: '人类偏好', group: 'safety', status: 'pending', benchmark_count: 0, has_composite: false },
  ],
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
      is_current: true, freshness_bucket: 'ACTIVE', lifecycle_status: 'ga',
    },
    {
      model_id: 'glm-5.3', display_name: 'GLM-5.3', provider: 'Zhipu AI', family: 'glm',
      variant: null, region: 'cn', open_weights: true, license: null, modalities: ['text'],
      context_window: 200000, release_date: null, official_model_page: null,
      capability_indices: { reasoning: 88, coding: 85 },
      overall_index: 86.0, overall_rank: 2, overall_benchmark_count: 5, overall_source_count: 2,
      price_input_usd_per_mtok: 0.6, price_output_usd_per_mtok: 2.2, output_speed_tps: 90,
      latency_seconds: 0.5, benchmark_count: 5, source_count: 2, rank_changes: { reasoning: { d7: 2 } },
      is_current: false, freshness_bucket: 'LEGACY', lifecycle_status: 'deprecated',
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
  benchmarks: [{ benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', source_id: 'livebench', higher_is_better: true, score_unit: 'percent', record_count: 2, eligible_for_composite: true }],
  official: [
    {
      benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', capability: 'reasoning',
      source_id: 'livebench', source_name: 'LiveBench（官方）', source_level: 'B', source_url: 'https://livebench.ai/',
      model_id: 'gpt-5.2-high', raw_model_name: 'gpt-5.2-2025-12-11-high', model_is_unmapped: false,
      score: 96.2, score_unit: 'percent', higher_is_better: true, rank: 1, tie: false,
      evaluation_date: '2026-06-25', evaluation_target_type: 'base_model', agent_scaffold: null,
      prompt_mode: null, benchmark_version: '2026-06-25', sample_size: 24, notes: 'test',
      fetched_at: '2026-08-30T00:00:00Z', provider: 'OpenAI', region: 'us', open_weights: false,
      record_verification_status: 'maintainer_verified',
      data_file_url: 'https://livebench.ai/table.csv', data_json_path: 'csv: model=x', data_sha256: 'abc',
    },
    {
      benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', capability: 'reasoning',
      source_id: 'livebench', source_name: 'LiveBench（官方）', source_level: 'B', source_url: 'https://livebench.ai/',
      model_id: 'glm-5.3', raw_model_name: 'glm-5.3', model_is_unmapped: false,
      score: 90.1, score_unit: 'percent', higher_is_better: true, rank: 2, tie: false,
      evaluation_date: '2026-06-25', evaluation_target_type: 'base_model', agent_scaffold: null,
      prompt_mode: null, benchmark_version: '2026-06-25', sample_size: 24, notes: 'test',
      fetched_at: '2026-08-30T00:00:00Z', provider: 'Zhipu AI', region: 'cn', open_weights: true,
      record_verification_status: 'maintainer_verified',
      data_file_url: 'https://livebench.ai/table.csv', data_json_path: 'csv: model=y', data_sha256: 'abc',
      is_current: false, freshness_bucket: 'LEGACY',
    },
    {
      benchmark_id: 'livebench-reasoning', benchmark_name: 'LiveBench 逻辑推理', capability: 'reasoning',
      source_id: 'livebench', source_name: 'LiveBench（官方）', source_level: 'B', source_url: 'https://livebench.ai/',
      model_id: 'unmapped--livebench--old-model', raw_model_name: 'Old-2024-Model', model_is_unmapped: true,
      score: 99.9, score_unit: 'percent', higher_is_better: true, rank: 1, tie: false,
      evaluation_date: '2024-01-01', evaluation_target_type: 'base_model', agent_scaffold: null,
      prompt_mode: null, benchmark_version: '2026-06-25', sample_size: 24, notes: '',
      fetched_at: '2026-08-30T00:00:00Z', provider: null, region: null, open_weights: null,
      record_verification_status: 'unknown',
      data_file_url: 'https://livebench.ai/table.csv', data_json_path: 'csv: model=z', data_sha256: 'abc',
    },
  ],
  composite: null,
  composite_gate: [{ reason: '单一合格基准，不产生综合' }],
};

const capabilitySwe = {
  capability_id: 'swe',
  name: '软件工程（模型 + Agent 系统）',
  short: '软件工程',
  status: 'active',
  description: 'SWE-bench Verified 记录代表模型与 Agent 框架的完整系统表现。',
  generated_at: '2026-08-30T00:00:00Z',
  benchmarks: [{ benchmark_id: 'swebench-verified', benchmark_name: 'SWE-bench Verified', source_id: 'swebench', higher_is_better: true, score_unit: 'percent', record_count: 2, eligible_for_composite: false }],
  official: [
    {
      benchmark_id: 'swebench-verified', benchmark_name: 'SWE-bench Verified', capability: 'swe',
      source_id: 'swebench', source_name: 'SWE-bench（官方）', source_level: 'A', source_url: 'https://www.swebench.com/',
      model_id: 'gpt-5.2-high', raw_model_name: 'gpt-5.2-high', model_is_unmapped: false,
      score: 78.2, score_unit: 'percent', higher_is_better: true, rank: 2, tie: false,
      evaluation_date: '2026-02-17', evaluation_target_type: 'model_plus_agent', agent_scaffold: 'mini-SWE-agent',
      prompt_mode: 'high', benchmark_version: 'verified', sample_size: 500, notes: 'test',
      fetched_at: '2026-08-30T00:00:00Z', record_verification_status: 'maintainer_verified',
      data_file_url: 'https://www.swebench.com/verified.json', data_json_path: '$[0]', data_sha256: 'abc',
    },
    {
      benchmark_id: 'swebench-verified', benchmark_name: 'SWE-bench Verified', capability: 'swe',
      source_id: 'swebench', source_name: 'SWE-bench（官方）', source_level: 'A', source_url: 'https://www.swebench.com/',
      model_id: 'unmapped--swebench--doubao-seed-code', raw_model_name: 'Doubao-Seed-Code', model_is_unmapped: true,
      score: 88.8, score_unit: 'percent', higher_is_better: true, rank: 1, tie: false,
      evaluation_date: '2025-07-26', evaluation_target_type: 'model_plus_agent', agent_scaffold: 'OpenHands',
      prompt_mode: null, benchmark_version: 'verified', sample_size: 500, notes: 'legacy without freshness metadata',
      fetched_at: '2026-08-30T00:00:00Z', record_verification_status: 'third_party_submitted',
      data_file_url: 'https://www.swebench.com/verified.json', data_json_path: '$[1]', data_sha256: 'abc',
    },
  ],
  composite: null,
  composite_gate: [{ reason: 'Agent 系统不生成基础模型综合' }],
};

const heatmap = {
  generated_at: '2026-08-30T00:00:00Z',
  capabilities: [
    {
      capability_id: 'reasoning', benchmark_id: 'livebench-reasoning', higher_is_better: true, score_unit: 'percent',
      cells: [
        { model_id: 'gpt-5.2-high', display_name: 'GPT-5.2 High', provider: 'OpenAI', score: 96.2, rank: 1, tie: false, agent_scaffold: null, evaluation_date: '2026-06-25' },
        { model_id: 'glm-5.3', display_name: 'GLM-5.3', provider: 'Zhipu AI', score: 90.1, rank: 2, tie: false, agent_scaffold: null, evaluation_date: '2026-06-25' },
      ],
    },
  ],
  models: ['gpt-5.2-high', 'glm-5.3'],
};

const homepage = {
  generated_at: meta.generated_at,
  stats: meta.counts,
  update: meta.update,
  top3: { reasoning: { rows: [{ model_id: 'gpt-5.2-high', display_name: 'GPT-5.2 High', provider: 'OpenAI', score: 96.2, rank: 1, benchmark_id: 'livebench-reasoning', kind: 'official' }], current_count: 1, total_rows: 2, benchmark_id: 'livebench-reasoning' } },
  latest_releases: { '7d': [], '30d': [{ model_id: 'qwen-3.8-27b', name: 'Qwen 3.8 27B', provider_id: 'alibaba', release_date: '2026-08-14', last_updated: '2026-08-14', status: null, lifecycle_status: 'ga', open_weights: true, reasoning: true, tool_call: true, context_window: 262144, input_price: 0.3, output_price: 1.2 }], '90d': [] },
  movers_7d: [{ model_id: 'glm-5.3', display_name: 'GLM-5.3', provider: 'Zhipu AI', capability: 'reasoning', delta: 2 }],
  trend_30d: [],
};

function baseMocks() {
  return mockFetch({
    '/data/meta.json': meta,
    '/data/homepage.json': homepage,
    '/data/models/index.json': modelsIndex,
    '/data/capabilities/index.json': capabilitiesIndex,
    '/data/capabilities/reasoning.json': capabilityReasoning,
    '/data/capabilities/swe.json': capabilitySwe,
    '/data/heatmap.json': heatmap,
    '/data/source-health.json': { generated_at: '', counts: { healthy: 2, degraded: 0, failed: 0, disabled: 3 }, sources: [] },
  });
}

describe('前端核心路径（V2 口径）', () => {
  beforeEach(() => {
    clearCache();
    window.location.hash = '#/';
    vi.stubGlobal('fetch', baseMocks());
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('首页正常加载：官方榜为主、相对口径标注可见', async () => {
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText('全球 AI 模型能力')).toBeInTheDocument());
    // 官方原始分榜单出现（默认推理 Tab）
    await waitFor(() => expect(screen.getAllByText('gpt-5.2-2025-12-11-high').length).toBeGreaterThan(0));
    // 状态圆点存在于全局导航
    expect(screen.getByLabelText(/数据状态/)).toBeInTheDocument();
    // 官方榜 Tab 存在
    expect(screen.getByRole('button', { name: '文本推理' })).toBeInTheDocument();
  });

  it('首页热力图渲染官方原始分', async () => {
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText('能力 × 模型热力图')).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText('96.2').length).toBeGreaterThan(0));
  });

  it('榜单页支持搜索筛选', async () => {
    window.location.hash = '#/leaderboard?cap=reasoning';
    render(<HashRouter><App /></HashRouter>);
    expect(await screen.findAllByText(/LiveBench 逻辑推理/).then((els) => els.length)).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('tab', { name: /HISTORY/ }));
    const input = screen.getByLabelText('搜索模型');
    fireEvent.change(input, { target: { value: 'glm' } });
    await waitFor(() => expect(screen.queryAllByText('gpt-5.2-2025-12-11-high').length).toBe(0));
    expect(screen.getAllByText('glm-5.3').length).toBeGreaterThan(0);
  });

  it('Agent 榜默认 fail-closed 为 CURRENT，并分列发布与评测日期', async () => {
    window.location.hash = '#/leaderboard?cap=swe';
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getAllByText(/SWE-bench Verified/).length).toBeGreaterThan(0));

    expect(screen.getByRole('tab', { name: /CURRENT/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('Doubao-Seed-Code')).not.toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Agent 框架/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /发布日期/ })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /评测日期/ })).toBeInTheDocument();
    expect(screen.getAllByText('2025-12-11').length).toBeGreaterThan(0);
    expect(screen.getAllByText('2026-02-17').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('tab', { name: /HISTORY/ }));
    expect(await screen.findByText('Doubao-Seed-Code')).toBeInTheDocument();
  });

  it('相对百分位为次级且单基准能力被门槛禁用', async () => {
    window.location.hash = '#/leaderboard?cap=reasoning';
    render(<HashRouter><App /></HashRouter>);
    await screen.findAllByRole('tab', { name: /本站相对百分位/ }).then((tabs) => {
      expect(tabs[0]).toHaveAttribute('disabled'); // mock 数据为单基准 -> 门槛禁用
    });
    expect(screen.getAllByText(/仅提供官方原始榜/).length).toBeGreaterThan(0);
  });

  it('点击分数打开溯源抽屉并显示验证状态与数据年龄', async () => {
    window.location.hash = '#/leaderboard?cap=reasoning';
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getAllByText('96.2').length).toBeGreaterThan(0));
    const btn = screen.getAllByText('96.2')[0];
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByText('数据溯源 · Data Provenance')).toBeInTheDocument());
    expect(screen.getByText('官方核验')).toBeInTheDocument();
    expect(screen.getAllByText(/数据年龄/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/精确数据文件/).length).toBeGreaterThan(0);
  });

  it('Latest Releases 展示目录数据（非 benchmark 日期冒充）', async () => {
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText('最新发布')).toBeInTheDocument());
    expect(await screen.findByText('Qwen 3.8 27B')).toBeInTheDocument();
    expect(screen.getByText('2026-08-14')).toBeInTheDocument();
  });

  it('首页默认仅当前模型：unmapped 与 legacy 不进主榜', async () => {
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getAllByText('gpt-5.2-2025-12-11-high').length).toBeGreaterThan(0));
    // 未映射模型禁止出现在首页
    expect(screen.queryAllByText('Old-2024-Model').length).toBe(0);
    expect(screen.queryAllByText(/unmapped--/).length).toBe(0);
    // legacy 不在默认视图
    expect(screen.queryByText('Old-2024-Model')).toBeNull();
  });

  it('数据缺失时显示空状态而非模拟数据', async () => {
    clearCache();
    window.location.hash = '#/';
    vi.stubGlobal('fetch', mockFetch({}));
    render(<HashRouter><App /></HashRouter>);
    await waitFor(() => expect(screen.getByText(/暂无已验证数据/)).toBeInTheDocument());
  });
});
