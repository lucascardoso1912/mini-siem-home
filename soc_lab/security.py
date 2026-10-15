"""Bounded request protection for the local SOC API."""

import json
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable
from typing import Any

ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]], Awaitable[None]]


class _RequestBodyTooLarge(Exception):
    pass


class ApiProtectionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 120,
        writes_per_minute: int = 20,
        global_requests_per_minute: int = 600,
        max_body_bytes: int = 65_536,
        max_tracked_clients: int = 4096,
    ) -> None:
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.writes_per_minute = writes_per_minute
        self.global_requests_per_minute = global_requests_per_minute
        self.max_body_bytes = max_body_bytes
        self.max_tracked_clients = max_tracked_clients
        self.window_seconds = 60.0
        self._buckets: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._last_cleanup = 0.0

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < self.window_seconds:
            return
        cutoff = now - self.window_seconds
        for key, bucket in list(self._buckets.items()):
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                del self._buckets[key]
        self._last_cleanup = now

    def _consume(self, key: tuple[str, str], limit: int, now: float) -> int | None:
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.max_tracked_clients:
                self._buckets.popitem(last=False)
            bucket = deque()
            self._buckets[key] = bucket

        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        self._buckets.move_to_end(key)

        if len(bucket) >= limit:
            return max(1, int(self.window_seconds - (now - bucket[0])))
        bucket.append(now)
        return None

    @staticmethod
    def _security_headers(include_csp: bool = False) -> list[tuple[bytes, bytes]]:
        headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        ]
        if include_csp:
            headers.append(
                (
                    b"content-security-policy",
                    b"default-src 'self'; script-src 'self'; style-src 'self'; "
                    b"connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                    b"base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
                )
            )
        return headers

    async def _respond(
        self,
        send: Callable[..., Awaitable[Any]],
        status: int,
        detail: str,
        retry_after: int | None = None,
    ) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
            *self._security_headers(),
        ]
        if retry_after is not None:
            headers.append((b"retry-after", str(retry_after).encode("ascii")))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[Any]],
        send: Callable[..., Awaitable[Any]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        self._cleanup(now)
        client = scope.get("client")
        client_ip = str(client[0]) if client else "unknown"
        method = scope.get("method", "GET").upper()
        global_retry = self._consume(("*", "global"), self.global_requests_per_minute, now)
        if global_retry is not None:
            await self._respond(send, 429, "Global request limit exceeded", global_retry)
            return

        is_write = method in {"POST", "PUT", "PATCH", "DELETE"}
        bucket_name = "write" if is_write else "read"
        limit = self.writes_per_minute if is_write else self.requests_per_minute
        client_retry = self._consume((client_ip, bucket_name), limit, now)
        if client_retry is not None:
            await self._respond(send, 429, "Client request limit exceeded", client_retry)
            return

        content_length = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._respond(send, 400, "Invalid Content-Length")
                return
            if declared_length < 0:
                await self._respond(send, 400, "Invalid Content-Length")
                return
            if declared_length > self.max_body_bytes:
                await self._respond(send, 413, "Request body too large")
                return

        async def secure_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                include_csp = scope.get("path") in {"/", "/index.html"}
                headers.extend(
                    (name, value)
                    for name, value in self._security_headers(include_csp)
                    if name not in present
                )
                message["headers"] = headers
            await send(message)

        received_bytes = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, secure_send)
        except _RequestBodyTooLarge:
            await self._respond(send, 413, "Request body too large")