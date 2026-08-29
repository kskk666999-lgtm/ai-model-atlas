"""适配器注册表：source_id -> 适配器实现。

disabled 的来源（livecodebench / opencompass_text / arena）没有适配器，
由 update.py 依据 sources.yml 直接标记为 disabled。
"""
from .artificialanalysis import ArtificialAnalysisAdapter
from .base import AdapterError, BaseAdapter, build_adapter_runtime
from .bigcodebench import BigCodeBenchAdapter
from .livebench import LiveBenchAdapter
from .mteb import MTEBAdapter
from .swebench import SWEBenchAdapter
from .vlmevalkit import VLMEvalKitAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "livebench": LiveBenchAdapter,
    "swebench": SWEBenchAdapter,
    "bigcodebench": BigCodeBenchAdapter,
    "vlmevalkit": VLMEvalKitAdapter,
    "mteb": MTEBAdapter,
    "artificialanalysis": ArtificialAnalysisAdapter,
}

__all__ = [
    "ADAPTERS",
    "AdapterError",
    "ArtificialAnalysisAdapter",
    "BaseAdapter",
    "BigCodeBenchAdapter",
    "LiveBenchAdapter",
    "MTEBAdapter",
    "SWEBenchAdapter",
    "VLMEvalKitAdapter",
    "build_adapter_runtime",
]
