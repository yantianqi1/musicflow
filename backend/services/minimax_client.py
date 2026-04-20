import asyncio
import logging
import httpx
from backend.config import MINIMAX_API_KEY, MINIMAX_BASE_URL
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# MiniMax error codes that are transient and safe to retry
_RETRYABLE_CODES = {1002, 2151}
_MAX_RETRIES = 5
_RETRY_DELAYS = [3, 8, 15, 30, 60]  # seconds – longer backoff for RPM limits


class MinimaxClient:
    def __init__(self):
        self.base_url = MINIMAX_BASE_URL.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
        }

    def _resolve(self, endpoint: str) -> str:
        """Avoid double /v1 when base_url already ends with /v1."""
        if self.base_url.endswith("/v1") and endpoint.startswith("/v1"):
            return endpoint[3:]  # strip leading /v1
        return endpoint

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=120.0)

    def _check_resp(self, data: dict) -> None:
        status_code = data.get("base_resp", {}).get("status_code", -1)
        if status_code != 0:
            msg = data.get("base_resp", {}).get("status_msg", "未知错误")
            raise HTTPException(
                status_code=502,
                detail=f"MiniMax API 错误: {msg} (code={status_code})",
            )

    async def post(self, endpoint: str, payload: dict) -> dict:
        last_exc = None
        resolved = self._resolve(endpoint)
        for attempt in range(_MAX_RETRIES):
            async with self._client() as client:
                logger.info("MiniMax POST %s payload=%s", resolved, {k: (v if k != "audio_base64" else "...") for k, v in payload.items()})
                resp = await client.post(resolved, json=payload)
                resp.raise_for_status()
                data = resp.json()
                status_code = data.get("base_resp", {}).get("status_code", -1)
                if status_code == 0:
                    logger.info("MiniMax POST %s 成功 (trace=%s)", resolved, data.get("trace_id", "?"))
                    return data
                msg = data.get("base_resp", {}).get("status_msg", "")
                if status_code in _RETRYABLE_CODES and attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning("MiniMax POST %s 可重试错误 (code=%s, msg=%s), %d秒后第%d次重试", resolved, status_code, msg, delay, attempt + 2)
                    last_exc = HTTPException(status_code=502, detail=f"MiniMax API 错误: {msg} (code={status_code})")
                    await asyncio.sleep(delay)
                    continue
                logger.error("MiniMax POST %s 失败 (code=%s, msg=%s)", resolved, status_code, msg)
                self._check_resp(data)
        raise last_exc

    async def get(self, endpoint: str, params: dict | None = None) -> dict:
        async with self._client() as client:
            resp = await client.get(self._resolve(endpoint), params=params)
            resp.raise_for_status()
            data = resp.json()
            self._check_resp(data)
            return data

    async def upload_file(self, file_bytes: bytes, filename: str, purpose: str) -> dict:
        headers = {"Authorization": f"Bearer {MINIMAX_API_KEY}"}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=60.0) as client:
            resp = await client.post(
                self._resolve("/v1/files/upload"),
                headers=headers,
                data={"purpose": purpose},
                files={"file": (filename, file_bytes)},
            )
            resp.raise_for_status()
            return resp.json()


minimax = MinimaxClient()
