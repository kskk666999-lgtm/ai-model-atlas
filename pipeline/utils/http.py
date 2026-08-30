"""带缓存 / 重试 / 限速 / 合理 UA 的 HTTP 客户端。

- ETag / Last-Modified 协商缓存（磁盘缓存，304 命中零成本）
- tenacity 指数退避，最多 3 次重试
- 每个来源独立最小请求间隔（限速）
- 明确的 User-Agent，绝不伪装浏览器
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..paths import HTTP_CACHE_DIR

USER_AGENT = (
    "ai-model-atlas/0.1 (+https://github.com/ai-model-atlas/ai-model-atlas; "
    "open data pipeline; contact: repository issues)"
)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class HttpClient:
    def __init__(
        self,
        timeout: float = 30.0,
        min_interval_seconds: float = 0.25,
        cache_dir: Path | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
        )
        self._min_interval = min_interval_seconds
        self._last_request_ts = 0.0
        self._lock = threading.Lock()
        self._cache_dir = Path(cache_dir or HTTP_CACHE_DIR)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _throttle(self) -> None:
        with self._lock:
            wait = self._min_interval - (time.monotonic() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    @staticmethod
    def _cache_key(url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _meta_path(self, url: str) -> Path:
        return self._cache_dir / f"{self._cache_key(url)}.meta.json"

    def _body_path(self, url: str) -> Path:
        return self._cache_dir / f"{self._cache_key(url)}.body"

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, req_headers: dict[str, str]) -> httpx.Response:
        self._throttle()
        resp = self._client.get(url, headers=req_headers)
        if resp.status_code >= 400:
            resp.raise_for_status()
        return resp

    def get(self, url: str, use_cache: bool = True) -> bytes:
        """GET 文本/二进制内容；带 ETag/Last-Modified 缓存。"""
        req_headers: dict[str, str] = {}
        meta_path = self._meta_path(url)
        body_path = self._body_path(url)
        meta: dict = {}
        if use_cache and meta_path.exists() and body_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("etag"):
                req_headers["If-None-Match"] = meta["etag"]
            if meta.get("last_modified"):
                req_headers["If-Modified-Since"] = meta["last_modified"]

        try:
            resp = self._get(url, req_headers)
        except httpx.HTTPStatusError:
            # 协商缓存失效等网络问题下，退回最近一次成功缓存
            if use_cache and meta and body_path.exists():
                return body_path.read_bytes()
            raise
        except (httpx.TimeoutException, httpx.TransportError):
            if use_cache and meta and body_path.exists():
                return body_path.read_bytes()
            raise

        if resp.status_code == 304 and body_path.exists():
            return body_path.read_bytes()

        body = resp.content
        if use_cache:
            meta_new = {
                "url": url,
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            body_path.write_bytes(body)
            meta_path.write_text(json.dumps(meta_new, ensure_ascii=False), encoding="utf-8")
        return body

    def get_json(self, url: str, use_cache: bool = True):
        return json.loads(self.get(url, use_cache=use_cache).decode("utf-8"))

    def metadata(self, url: str) -> dict:
        """Return cached response metadata for an already fetched URL.

        Adapters use this to distinguish an upstream file snapshot date from a
        benchmark version or a per-model evaluation date. Missing/corrupt
        metadata is intentionally non-fatal because provenance fields are
        nullable by contract.
        """
        path = self._meta_path(url)
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def close(self) -> None:
        self._client.close()


def http_date_to_iso(value: str | None) -> str | None:
    """Convert an HTTP-date header to a stable UTC ISO timestamp."""
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
