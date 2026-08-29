"""历史排名快照：每日一份 JSON，保留策略自动聚合，防止仓库无限膨胀。

- 最近 90 天：保留每日快照
- 90 天 ~ 2 年：按 ISO 周聚合（保留每周最后一份）
- 超过 2 年：按月聚合
- 新数据删除某模型时不回溯修改历史；前台据"当前榜单缺席"自行提示。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from ..paths import SNAPSHOTS_DIR

DAILY_KEEP_DAYS = 90
WEEKLY_KEEP_DAYS = 730


class HistoryStore:
    def __init__(self, snapshots_dir: Path = SNAPSHOTS_DIR) -> None:
        self.dir = Path(snapshots_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _file_for(self, d: date) -> Path:
        return self.dir / f"{d.isoformat()}.json"

    def append_snapshot(self, d: date, payload: dict) -> None:
        """写入/覆盖当日快照。payload = {capability_id: {model_id: {index, rank}}}"""
        self._file_for(d).write_text(
            json.dumps({"date": d.isoformat(), **payload}, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_snapshots(self) -> list[dict]:
        files = sorted(self.dir.glob("*.json"))
        out = []
        for f in files:
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return out

    def apply_retention(self, today: date) -> int:
        """按保留策略聚合旧快照，返回清理/聚合的文件数。"""
        files = sorted(self.dir.glob("*.json"))
        by_key: dict[str, dict] = {}
        removed = 0
        for f in files:
            try:
                snap = json.loads(f.read_text(encoding="utf-8"))
                d = date.fromisoformat(snap["date"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            age_days = (today - d).days
            if age_days <= DAILY_KEEP_DAYS:
                key = d.isoformat()
            elif age_days <= WEEKLY_KEEP_DAYS:
                iso = d.isocalendar()
                key = f"{iso[0]}-W{iso[1]:02d}"
            else:
                key = f"{d.year}-{d.month:02d}"
            by_key[key] = snap  # 同 key 保留最新（文件名升序遍历）
            if key != d.isoformat():
                f.unlink()
                removed += 1
        for _key, snap in by_key.items():
            target = self.dir / f"{snap['date']}.json"
            if not target.exists():
                target.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8", newline="\n")
        return removed

    def rank_changes(self, today: date) -> dict[str, dict[str, dict]]:
        """计算 7 天 / 30 天排名变化：{model_id: {capability: {d7, d30}}}。

        变化 = 基准排名 - 当前排名（正数=上升）。取时间最近的、且 >=N 天前的快照。
        """
        snaps = [s for s in self.load_snapshots() if s.get("date")]
        snaps.sort(key=lambda s: s["date"])

        def find_baseline(days: int) -> dict | None:
            target = today - timedelta(days=days)
            candidates = [s for s in snaps if date.fromisoformat(s["date"]) <= target]
            return candidates[-1] if candidates else None

        latest = snaps[-1] if snaps else None
        base7 = find_baseline(7)
        base30 = find_baseline(30)
        if not latest:
            return {}

        changes: dict[str, dict[str, dict]] = defaultdict(dict)
        for cap, models in latest.items():
            if not isinstance(models, dict) or cap == "date":
                continue
            for model_id, cur in models.items():
                entry: dict[str, float] = {}
                for label, base in (("d7", base7), ("d30", base30)):
                    if base and cap in base and isinstance(base[cap], dict) \
                            and model_id in base[cap] and isinstance(base[cap][model_id], dict):
                        prev_rank = base[cap][model_id].get("rank")
                        cur_rank = cur.get("rank")
                        if isinstance(prev_rank, (int, float)) and isinstance(cur_rank, (int, float)):
                            entry[label] = float(prev_rank) - float(cur_rank)
                if entry:
                    changes[model_id][cap] = entry
        return dict(changes)

    def series_for(self, model_id: str, caps: list[str]) -> dict[str, list[dict]]:
        """单个模型、指定能力的 {date, rank, index} 序列（用于详情页趋势）。"""
        series: dict[str, list[dict]] = defaultdict(list)
        for snap in self.load_snapshots():
            for cap in caps:
                models = snap.get(cap)
                if isinstance(models, dict) and model_id in models:
                    series[cap].append({
                        "date": snap["date"],
                        "rank": models[model_id].get("rank"),
                        "index": models[model_id].get("index"),
                    })
        return dict(series)

    def trend_30d(self) -> list[dict]:
        """最近 30 天快照概览（首页趋势图）。"""
        today = date.today()
        snaps = [
            s for s in self.load_snapshots()
            if s.get("date") and today - date.fromisoformat(s["date"]) <= timedelta(days=30)
        ]
        snaps.sort(key=lambda s: s["date"])
        return [
            {
                "date": s["date"],
                "models": max(
                    (len(v) for k, v in s.items() if isinstance(v, dict) and k != "date"),
                    default=0,
                ),
                "capabilities": sum(1 for k, v in s.items() if isinstance(v, dict) and k != "date"),
            }
            for s in snaps
        ]
