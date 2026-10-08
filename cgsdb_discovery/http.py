"""Filename: cgsdb_discovery/http.py"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import random
from typing import Any

import aiohttp


class AsyncHttpClient:
    """Shared non-blocking HTTP client with bounded concurrency and retry/backoff."""

    def __init__(
        self,
        *,
        concurrency: int = 8,
        timeout_seconds: float = 20.0,
        user_agent: str = "commercial-games-source-database-2026-discovery/0.4",
        per_host_delay: float = 0.35,
        max_retries: int = 3,
    ) -> None:
        self.concurrency = max(1, concurrency)
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.user_agent = user_agent
        self.per_host_delay = max(0.0, per_host_delay)
        self.max_retries = max(0, max_retries)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AsyncHttpClient":
        self._session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent, "Accept": "*/*"},
            raise_for_status=False,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _pace(self, host: str) -> None:
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait = self.per_host_delay - (now - self._last_request.get(host, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request[host] = loop.time()

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | list[tuple[str, Any]] | None = None,
        data: str | bytes | Mapping[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        if self._session is None:
            raise RuntimeError("AsyncHttpClient must be used as an async context manager")

        last_error = ""
        for attempt in range(self.max_retries + 1):
            host = aiohttp.client_reqrep.URL(url).host or ""
            async with self._semaphore:
                await self._pace(host)
                try:
                    async with self._session.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        data=data,
                    ) as response:
                        text = await response.text(errors="replace")
                        headers_out = {k.lower(): v for k, v in response.headers.items()}
                        if response.status in {408, 425, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                            retry_after = float(headers_out.get("retry-after", "0") or 0)
                            delay = retry_after if retry_after > 0 else min(30.0, 2.0 ** attempt + random.random())
                            await asyncio.sleep(delay)
                            continue
                        return response.status, headers_out, text
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = str(exc)
                    if attempt >= self.max_retries:
                        raise
                    await asyncio.sleep(min(30.0, 2.0 ** attempt + random.random()))
        raise RuntimeError(last_error or "request failed")
