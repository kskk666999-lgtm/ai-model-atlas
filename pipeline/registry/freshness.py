"""模型新鲜度与生命周期判定（集中式，禁止散落多处）。

所有判断动态读取当前 UTC 日期，不硬编码任何年份/模型名。
桶阈值与当前资格规则在此统一定义，可配置。
"""
from __future__ import annotations

from datetime import UTC, date, datetime

# 新鲜度桶（天）：NEW 0-30 / FRESH 31-90 / ACTIVE 91-180 / AGING 181-365 / LEGACY >365
FRESHNESS_BUCKETS: list[tuple[str, int]] = [
    ("NEW", 30),
    ("FRESH", 90),
    ("ACTIVE", 180),
    ("AGING", 365),
]
LEGACY_BUCKET = "LEGACY"

# 生命周期状态（来自目录上游或推导）
LIFECYCLE_DEPRECATED = {"deprecated", "sunset", "legacy", "retired"}


def today_utc() -> date:
    return datetime.now(UTC).date()


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10] if fmt != "%Y%m%d" else value[:8], fmt).date()
        except ValueError:
            continue
    return None


def freshness_bucket(days: int | None) -> str:
    if days is None:
        return "UNKNOWN"
    for name, limit in FRESHNESS_BUCKETS:
        if days <= limit:
            return name
    return LEGACY_BUCKET


def freshness_days(release_date: str | None, last_updated: str | None = None,
                   today: date | None = None) -> int | None:
    """模型新鲜度 = 当前日期 - 发布日期（优先）；缺失时用 last_updated。"""
    today = today or today_utc()
    d = parse_date(release_date) or parse_date(last_updated)
    if d is None:
        return None
    return max(0, (today - d).days)


def lifecycle_status(upstream_status: str | None, bucket: str,
                     release_date: str | None = None) -> str:
    """生命周期：上游明确标注优先（deprecated/beta 等）；否则由新鲜度推导。"""
    if upstream_status:
        s = upstream_status.strip().lower()
        if s in LIFECYCLE_DEPRECATED:
            return "deprecated"
        if s in {"beta", "alpha", "preview"}:
            return "preview"
        if s in {"ga", "active", "stable"}:
            return "ga"
    if bucket == LEGACY_BUCKET:
        # 发布超过 365 天：标记 legacy，但不武断"删除"——历史榜仍完整保留
        return "legacy"
    if bucket == "UNKNOWN":
        return "unknown"
    return "ga"


def is_current(*, lifecycle: str, bucket: str,
               seen_in_latest_official_board: bool = False) -> bool:
    """当前模型资格（Current Model Eligibility Engine 的核心判定）。

    - lifecycle 为 deprecated/sunset/legacy → 不算当前
    - 新鲜度桶为 LEGACY → 不算当前
    - 元数据缺失（UNKNOWN）时的保守兜底：模型出现在活跃来源的"最新官方榜"上
      （如 LiveBench 当前 release 表、SWE-bench 近期核验运行），视为当前；
      否则不算当前（宁可少展示，不让旧模型冒充现役）。
    """
    if lifecycle in LIFECYCLE_DEPRECATED or lifecycle == "legacy":
        return False
    if bucket == LEGACY_BUCKET:
        return False
    if bucket == "UNKNOWN":
        return seen_in_latest_official_board
    return True
