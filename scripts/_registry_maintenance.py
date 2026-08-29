import yaml

path = 'data/registry/models.yml'
models = yaml.safe_load(open(path, encoding='utf-8'))['models']
by_id = {m['canonical_id']: m for m in models}

def entry(cid, display, provider, family=None, variant=None, aliases=(), release=None,
          open_weights=None, license_=None, modalities=('text',), context=None, region=None,
          page=None):
    return {
        'canonical_id': cid, 'display_name': display, 'provider': provider,
        'family': family or cid, 'variant': variant, 'aliases': list(aliases),
        'release_date': release, 'status': 'active', 'region': region,
        'open_weights': open_weights, 'license': license_, 'modalities': list(modalities),
        'context_window': context, 'official_model_page': page,
        'deprecated': False, 'superseded_by': None,
    }

# ---- 修正错误合并的 legacy 条目 ----
fixes = {
    'internvl3-78b': {'aliases': ['InternVL3-78B'], 'family': 'internvl'},
    'qvq-72b-preview': {'aliases': ['qvq-72b-preview', 'QVQ-72B-Preview'], 'display_name': 'QVQ-72B-Preview'},
    'glm-4-plus': {'aliases': ['glm-4-plus', 'GLM-4-Plus']},
    'qwen3-235b-a22b': {'aliases': ['qwen3-235b-a22b', 'Qwen3-235B-A22B']},
    'deepseek-r1': {'aliases': ['deepseek-r1', 'deepseek-reasoner', 'DeepSeek-R1']},
    'deepseek-v3.1': {'aliases': ['deepseek-v3.1', 'DeepSeek-V3.1']},
    'kimi-k2': {'aliases': ['kimi-k2', 'Kimi-K2', 'Kimi-K2-Instruct', 'kimi-k2-instruct']},
}
for cid, patch in fixes.items():
    if cid in by_id:
        by_id[cid].update(patch)

# ---- 新增拆分后的独立版本 ----
new_entries = [
    entry('internvl2.5-78b', 'InternVL2.5-78B', 'Shanghai AI Lab', family='internvl', aliases=['InternVL2.5-78B'], open_weights=True, license_='MIT', region='cn'),
    entry('internvl2-76b', 'InternVL2-76B', 'Shanghai AI Lab', family='internvl', aliases=['InternVL2-76B'], open_weights=True, license_='MIT', region='cn'),
    entry('internvl3-38b', 'InternVL3-38B', 'Shanghai AI Lab', family='internvl', aliases=['InternVL3-38B'], open_weights=True, license_='MIT', region='cn'),
    entry('internvl3-9b', 'InternVL3-9B', 'Shanghai AI Lab', family='internvl', aliases=['InternVL3-9B'], open_weights=True, license_='MIT', region='cn'),
    entry('qwen2.5-vl-72b', 'Qwen2.5-VL-72B', 'Alibaba', family='qwen2.5-vl', variant='72b', aliases=['Qwen2.5-VL-72B', 'Qwen2.5-VL-72B-Instruct'], open_weights=True, license_='apache-2.0', modalities=['text', 'image', 'video'], region='cn'),
    entry('qwen3-235b-a22b-instruct-2507', 'Qwen3-235B-A22B-Instruct-2507', 'Alibaba', family='qwen3', aliases=['Qwen3-235B-A22B-Instruct-2507', 'qwen3-235b-a22b-instruct-2507'], open_weights=True, license_='apache-2.0', region='cn'),
    entry('deepseek-r1-0528', 'DeepSeek-R1-0528', 'DeepSeek', family='deepseek-r1', aliases=['DeepSeek-R1-0528', 'deepseek-r1-0528'], open_weights=True, license_='MIT', region='cn'),
    entry('deepseek-v3-0324', 'DeepSeek-V3-0324', 'DeepSeek', family='deepseek-v3', aliases=['DeepSeek-V3-0324', 'deepseek-v3-0324'], open_weights=True, license_='deepseek-license', region='cn'),
    entry('kimi-k2-0905', 'Kimi-K2-0905', 'Moonshot AI', family='kimi-k2', aliases=['Kimi-K2-0905', 'kimi-k2-0905'], open_weights=True, region='cn'),
    entry('gpt-4o-2024-05-13', 'GPT-4o (2024-05-13)', 'OpenAI', family='gpt-4o', release='2024-05-13', aliases=['gpt-4o-2024-05-13', 'GPT-4o (0513, detail-high)', 'GPT-4o (0513, detail-low)'], modalities=['text', 'image'], context=128000),
    entry('gpt-4o-2024-08-06', 'GPT-4o (2024-08-06)', 'OpenAI', family='gpt-4o', release='2024-08-06', aliases=['gpt-4o-2024-08-06', 'GPT-4o (0806, detail-high)', 'GPT-4o (0806, detail-low)'], modalities=['text', 'image'], context=128000),
    entry('gpt-4v-0409', 'GPT-4V (2024-04-09)', 'OpenAI', family='gpt-4v', aliases=['GPT-4v (0409, detail-low)', 'GPT-4v (0409, detail-high)'], modalities=['text', 'image']),
    entry('gpt-4v-1106', 'GPT-4V (2023-11)', 'OpenAI', family='gpt-4v', aliases=['GPT-4v (1106, detail-high)', 'GPT-4v (1106, detail-low)'], modalities=['text', 'image']),
    entry('gpt-5-nano-2025-08-07', 'GPT-5 nano', 'OpenAI', family='gpt-5', aliases=['gpt-5-nano-2025-08-07', 'GPT 5 nano'], release='2025-08-07'),
    entry('gemini-3-flash-preview', 'Gemini 3 Flash (Preview)', 'Google', family='gemini-3', aliases=['gemini-3-flash-preview', 'gemini-3-flash', 'Gemini 3 Flash', 'Gemini-3-Flash']),
    entry('deepseek-v3.2', 'DeepSeek-V3.2', 'DeepSeek', family='deepseek-v3', aliases=['deepseek-v3.2', 'DeepSeek V3.2'], open_weights=True, region='cn'),
    entry('deepseek-v3.2-reasoner', 'DeepSeek-V3.2 (Reasoner)', 'DeepSeek', family='deepseek-v3', aliases=['deepseek-v3.2-reasoner', 'DeepSeek V3.2 Reasoner'], open_weights=True, region='cn'),
    entry('glm-4.6', 'GLM-4.6', 'Zhipu AI', family='glm-4.6', aliases=['glm-4.6', 'GLM 4.6'], open_weights=True, region='cn'),
    entry('glm-5', 'GLM-5', 'Zhipu AI', family='glm-5', aliases=['glm-5', 'GLM 5'], region='cn'),
    entry('kimi-k2-thinking', 'Kimi K2 (Thinking)', 'Moonshot AI', family='kimi-k2', aliases=['kimi-k2-thinking', 'Kimi K2 Thinking', 'Kimi-K2-Thinking'], open_weights=True, region='cn'),
    entry('kimi-k2.5', 'Kimi K2.5', 'Moonshot AI', family='kimi-k2', aliases=['kimi-k2.5', 'Kimi K2.5'], region='cn'),
    entry('minimax-m2', 'MiniMax-M2', 'MiniMax', family='minimax-m', aliases=['minimax-m2', 'MiniMax M2', 'MiniMax-M2'], open_weights=True, region='cn'),
    entry('minimax-m2.5', 'MiniMax-M2.5', 'MiniMax', family='minimax-m', aliases=['minimax-m2.5', 'MiniMax M2.5', 'MiniMax-M2.5'], region='cn'),
    entry('devstral-2512', 'Devstral (2512)', 'Mistral AI', family='devstral', aliases=['devstral-2512', 'Devstral (2512)']),
    entry('devstral-small-2512', 'Devstral Small (2512)', 'Mistral AI', family='devstral', aliases=['devstral-small-2512', 'Devstral Small (2512)'], open_weights=True, license_='apache-2.0'),
    entry('qwen2.5-coder-32b-instruct', 'Qwen2.5-Coder-32B-Instruct', 'Alibaba', family='qwen2.5-coder', aliases=['qwen2.5-coder-32b-instruct', 'Qwen2.5-Coder-32B-Instruct', 'Qwen2.5-Coder 32B Instruct'], open_weights=True, license_='apache-2.0', region='cn'),
    entry('molmo-72b', 'Molmo-72B', 'Allen AI', family='molmo', aliases=['Molmo-72B', 'molmo-72b'], open_weights=True, modalities=['text', 'image']),
    entry('deepseek-vl2', 'DeepSeek-VL2', 'DeepSeek', family='deepseek-vl', aliases=['DeepSeek-VL2', 'deepseek-vl2'], modalities=['text', 'image'], region='cn'),
    entry('llava-onevision-72b', 'LLaVA-OneVision-72B', 'LLaVA', family='llava-onevision', aliases=['LLaVA-OneVision-72B'], open_weights=True, modalities=['text', 'image']),
    entry('step-1.5v', 'Step-1.5V', 'StepFun', family='step', aliases=['Step-1.5V', 'step-1.5v'], modalities=['text', 'image'], region='cn'),
    entry('glm-4v-plus', 'GLM-4V-Plus', 'Zhipu AI', family='glm-4v', aliases=['GLM-4v-Plus', 'GLM-4v-Plus-20250111', 'glm-4v-plus'], modalities=['text', 'image'], region='cn'),
    entry('ovis2-34b', 'Ovis2-34B', 'Ovis', family='ovis', aliases=['Ovis2-34B'], open_weights=True, modalities=['text', 'image']),
    entry('qwen-vl-max-0809', 'Qwen-VL-Max (0809)', 'Alibaba', family='qwen-vl', aliases=['Qwen-VL-Max-0809', 'qwen-vl-max-0809'], modalities=['text', 'image'], region='cn'),
    entry('claude-3-5-haiku-20241022', 'Claude 3.5 Haiku', 'Anthropic', family='claude-3.5', variant='haiku', aliases=['claude-3-5-haiku-20241022', 'claude-3-5-haiku-latest', 'Claude 3.5 Haiku'], release='2024-11-04', modalities=['text'], context=200000),
]

existing = {m['canonical_id'] for m in models}
models = models + [e for e in new_entries if e['canonical_id'] not in existing]

header = """# 模型注册表 —— 唯一权威的模型档案。
# 字段取不到真实值时必须写 null，禁止编造。
# canonical_id 使用数据源中最常见的规范写法；变体（thinking/effort/日期/参数量）一律独立条目，禁止错误合并。
# 需要人工映射的新名称会出现在 data/reports/unmapped-models.json。
"""
with open(path, 'w', encoding='utf-8') as f:
    f.write(header)
    f.write('models:\n')
    yaml.safe_dump(models, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=240)
print('total entries:', len(models))
