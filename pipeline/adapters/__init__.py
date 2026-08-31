"""适配器注册表：source_id -> 适配器实现。

disabled 的来源（livecodebench / opencompass_text / arena）没有适配器，
由 update.py 依据 sources.yml 直接标记为 disabled。
"""
from .artificialanalysis import ArtificialAnalysisAdapter
from .base import AdapterError, BaseAdapter, build_adapter_runtime
from .bfcl import BFCLAdapter
from .bigcodebench import BigCodeBenchAdapter
from .kernelbench import KernelBenchAdapter
from .livebench import LiveBenchAdapter
from .mteb import MTEBAdapter
from .superclue import SuperCLUEAdapter
from .superclue_longcontext import SuperCLUELongContextAdapter
from .superclue_vlm import SuperCLUEVLMAdapter
from .swebench import SWEBenchAdapter
from .terminalbench import TerminalBenchAdapter
from .vlmevalkit import VLMEvalKitAdapter

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "livebench": LiveBenchAdapter,
    "superclue": SuperCLUEAdapter,
    "superclue_longcontext": SuperCLUELongContextAdapter,
    "superclue_vlm": SuperCLUEVLMAdapter,
    "kernelbench": KernelBenchAdapter,
    "swebench": SWEBenchAdapter,
    "terminalbench": TerminalBenchAdapter,
    "bfcl": BFCLAdapter,
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
    "BFCLAdapter",
    "BigCodeBenchAdapter",
    "LiveBenchAdapter",
    "SuperCLUEAdapter",
    "SuperCLUELongContextAdapter",
    "SuperCLUEVLMAdapter",
    "KernelBenchAdapter",
    "MTEBAdapter",
    "SWEBenchAdapter",
    "TerminalBenchAdapter",
    "VLMEvalKitAdapter",
    "build_adapter_runtime",
]
