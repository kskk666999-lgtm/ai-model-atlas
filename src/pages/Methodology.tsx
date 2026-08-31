const SECTIONS: { title: string; body: React.ReactNode }[] = [
  {
    title: '一、数据来源等级（A / B / C / D）',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li><b className="text-emerald-300">A 级（权重 1.0）</b>：官方基准仓库 / 官方结构化结果文件 / 官方数据 API，有版本号、提交记录或可复现的评测材料。例如 SWE-bench experiments、MTEB results、BigCodeBench 官方结果、VLMEvalKit 官方汇总。</li>
        <li><b className="text-sky-300">B 级（权重 0.8）</b>：官方排行榜导出（官方生成但复现材料不完整），例如 LiveBench 官网按 release 发布的 table CSV。</li>
        <li><b className="text-amber-300">C 级（权重 0.6）</b>：有公开方法论的独立第三方评测（如 Artificial Analysis 免费 API，需注明来源）。</li>
        <li><b className="text-rose-300">D 级（权重 0，默认不收录）</b>：厂商自报成绩、发布会材料等无法验证的数据，本站默认不展示、不参与任何排名。</li>
      </ul>
    ),
  },
  {
    title: '二、模型名称规范化与版本纪律',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>所有来源的模型名先经过<b>显式别名表</b>映射到注册表 canonical_id。没有命中别名的名称不会丢弃，也不会被猜测合并——它们以来源原始名称出现在来源原始榜上，并写入 unmapped-models.json 等待人工补充别名。</li>
        <li><b>Thinking / Non-Thinking、High / Medium / Low effort、不同发布日期、不同上下文版本，一律是独立的模型条目</b>。本站绝不为了榜单整洁而错误合并不同版本。</li>
        <li>同一来源内部出现完全相同的 (基准, 模型, 变体, 版本) 记录时只保留一条；冲突分数则全部保留并告警。</li>
      </ul>
    ),
  },
  {
    title: '三、Agent 系统与基础模型分开',
    body: (
      <p>
        SWE-bench 等基准的提交反映的是「模型 + Agent 框架 + 工具 + 提示词 + 推理预算 + 环境」的完整系统。
        因此每条成绩都带 evaluation_target_type 标签：<span className="badge">基础模型</span> <span className="badge">API 端点</span>{' '}
        <span className="badge border-violet-400/40 bg-violet-400/10 text-violet-200">模型+Agent</span>。
        Agent 系统成绩：<b>不进入</b>基础模型综合指数；软件工程榜单独展示并显著标注。
      </p>
    ),
  },
  {
    title: '四、综合指数算法（本站计算，非官方）',
    body: (
      <div className="space-y-3">
        <p>综合指数永远基于「基准内百分位」，绝不直接平均不同基准的原始分：</p>
        <pre className="num overflow-x-auto rounded-xl bg-black/40 p-4 text-xs leading-6 text-cyan-100">{`1. benchmark_percentile(m, b)
     = 模型 m 在基准 b 内的百分位排名（0~100，并列取平均）
2. source_score(m, s) = 平均( benchmark_percentile(m, b) ),  b ∈ 来源 s
3. capability_score(m)
     = Σ source_score(m, s) × source_weight(s) / Σ source_weight(s)
     source_weight: A=1.0, B=0.8, C=0.6, D=0（不参与）
4. overall_index(m)
     = Σ capability_score(m, c) × w(c) / Σ w(c)   （权重预设可切换）
     仅统计该模型有数据的 c，缺失能力不按 0 分计入。`}</pre>
        <p>
          综合榜分两级展示：<b>多源验证综合榜（Beta）</b>只收录覆盖 ≥4 能力类别、≥5 基准、≥2 独立数据来源
          且全部为非 Agent 成绩的模型，可视为跨来源共识——当前满足条件的模型较少，这是规则的诚实结果而非数据缺失；
          <b>单源参考综合榜</b>收录有任意能力数据的全部模型，便于浏览对比，但行内标注"单源"的模型
          成绩仅来自一个数据来源，<b>不可视为多源共识</b>。两级榜单都展示来源数量与覆盖能力数量。
        </p>
        <p>能力只有一个可靠基准时，来源原始榜照常展示，综合指数标注「单一来源」，不伪装成多源共识。</p>
      </div>
    ),
  },
  {
    title: '五、缺失数据、并列与置信度',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li><b>缺失数据永远不是 0 分</b>——统一显示「暂无数据 / —」，只影响覆盖率与置信度展示。</li>
        <li>分数并列时采用 competition ranking（1, 2, 2, 4），并在界面上标注「并列·差异可能不显著」。</li>
        <li>每条综合指数都展示：来源数、基准数、是否单一来源、置信等级（高 / 中 / 低）。</li>
      </ul>
    ),
  },
  {
    title: '六、价格与性价比',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>价格区分输入 / 输出两个维度（USD / 1M tokens），来自 LiveBench 官方统计与（可选）Artificial Analysis API；价格未知的模型不进入价格榜。</li>
        <li>性价比指数在浏览器本地计算，公式公开：能力指数 ÷ 对应价格，可按综合 / 编程 / 中文 / 速度等视角切换。</li>
        <li>每百万 Token 价格反映标价，不代表实际账单（输出长度、缓存、推理 Token 等都会影响）。</li>
      </ul>
    ),
  },
  {
    title: '七、历史排名',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>每天保存一次快照：最近 90 天保留每日数据，90 天~2 年按周聚合，超过 2 年按月聚合，避免仓库无限膨胀。</li>
        <li>支持 7 天 / 30 天排名变化与历史趋势曲线。模型从来源消失时不会从历史中删除，前台标注「当前榜单缺席」。</li>
      </ul>
    ),
  },
  {
    title: '八、为什么本站部署后不消耗大模型 Token',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>网站是纯静态页面：浏览器只读取提前生成好的 JSON，图表全部在本地绘制。</li>
        <li>数据更新是普通 Python 抓取 + 确定性计算，每日计划更新两次（北京时间约 09:00 / 21:00（实际执行时间可能因 GitHub Actions 调度略有延迟）），不调用任何生成式模型 API。</li>
        <li>排名、综合指数、优势短板、场景推荐全部是确定性算法 / 规则，没有 LLM 参与。</li>
        <li>项目内置 <span className="num">scripts/verify-no-llm-runtime.py</span> 自动检查依赖与代码中不存在推理 API 调用。</li>
      </ul>
    ),
  },
  {
    title: '九、网站局限性',
    body: (
      <ul className="list-disc space-y-2 pl-5">
        <li>百分位指数衡量的是「相对位置」，同一能力下不同基准的难度差异被抹平；跨能力的指数不可直接比较绝对值。</li>
        <li>评测分数反映评测时点的端点行为，厂商更新模型后历史分数不会重算。</li>
        <li>综合指数高度依赖来源覆盖：覆盖来源少的模型指数波动更大，请结合置信度使用。</li>
        <li>未映射的模型名只出现在来源原始榜中，不参与跨来源综合，直到人工确认其身份。</li>
      </ul>
    ),
  },
];

export function MethodologyPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">方法论</h1>
        <p className="mt-1 text-sm text-slate-400">
          本页说明榜单的全部计算规则。所有规则都是公开且确定性的——没有任何黑盒评分或大模型参与。
        </p>
      </header>
      {SECTIONS.map((s) => (
        <section key={s.title} className="panel px-6 py-5">
          <h2 className="text-base font-bold text-slate-100">{s.title}</h2>
          <div className="mt-3 text-sm leading-7 text-slate-300">{s.body}</div>
        </section>
      ))}
    </div>
  );
}
