"""项目内常用路径（基于 pathlib，Windows 兼容）。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
REGISTRY_DIR = DATA_DIR / "registry"
CACHE_DIR = DATA_DIR / "cache"
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = DATA_DIR / "reports"
HISTORY_DIR = DATA_DIR / "history"
SNAPSHOTS_DIR = HISTORY_DIR / "snapshots"

PUBLIC_DIR = PROJECT_ROOT / "public"
PUBLIC_DATA_DIR = PUBLIC_DIR / "data"

REGISTRY_MODELS = REGISTRY_DIR / "models.yml"
REGISTRY_ALIASES = REGISTRY_DIR / "aliases.yml"
REGISTRY_SOURCES = REGISTRY_DIR / "sources.yml"
REGISTRY_BENCHMARKS = REGISTRY_DIR / "benchmarks.yml"
REGISTRY_CAPABILITIES = REGISTRY_DIR / "capability-weights.yml"

SOURCE_STATE_FILE = CACHE_DIR / "source-state.json"
RECORDS_LKG_DIR = CACHE_DIR / "records"
HTTP_CACHE_DIR = CACHE_DIR / "http"
UNMAPPED_FILE = REPORTS_DIR / "unmapped-models.json"
LATEST_UPDATE_JSON = REPORTS_DIR / "latest-update.json"
LATEST_UPDATE_MD = REPORTS_DIR / "latest-update.md"
