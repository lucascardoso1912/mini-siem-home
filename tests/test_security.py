import asyncio
import unittest
from typing import Any

from soc_lab.security import ApiProtectionMiddleware


class ApiProtectionMiddlewareTests(unittest.TestCase):
    def make_request(
        self,
        middleware: ApiProtectionMiddleware,
        *,
        body: bytes = b"",
        content_length: bytes | None = None,
        client_ip: str = "127.0.0.1",
        path: str = "/api/health",
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        headers = [] if content_length is None else [(b"content-length", content_length)]

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        async def app(scope: dict[str, Any], app_receive: Any, app_send: Any) -> None:
            await app_receive()
            await app_send({"type": "http.response.start", "status": 200, "headers": []})
            await app_send({"type": "http.response.body", "body": b"ok"})

        middleware.app = app
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": headers,
            "client": (client_ip, 12345),
        }
        asyncio.run(middleware(scope, receive, send))
        return messages

    def test_rate_limit_returns_429_and_retry_after(self) -> None:
        middleware = ApiProtectionMiddleware(
            lambda *_: None,
            requests_per_minute=1,
            global_requests_per_minute=10,
        )

        first = self.make_request(middleware)
        second = self.make_request(middleware)

        self.assertEqual(first[0]["status"], 200)
        self.assertEqual(second[0]["status"], 429)
        retry_after = dict(second[0]["headers"])[b"retry-after"]
        self.assertGreaterEqual(int(retry_after), 1)
        self.assertLessEqual(int(retry_after), 60)

    def test_global_rate_limit_applies_across_clients(self) -> None:
        middleware = ApiProtectionMiddleware(
            lambda *_: None,
            requests_per_minute=10,
            global_requests_per_minute=1,
        )

        self.make_request(middleware, client_ip="127.0.0.1")
        second = self.make_request(middleware, client_ip="127.0.0.2")

        self.assertEqual(second[0]["status"], 429)

    def test_rejects_oversized_body(self) -> None:
        middleware = ApiProtectionMiddleware(
            lambda *_: None,
            max_body_bytes=4,
        )

        response = self.make_request(
            middleware,
            body=b"12345",
            content_length=b"5",
        )

        self.assertEqual(response[0]["status"], 413)

    def test_adds_security_headers(self) -> None:
        middleware = ApiProtectionMiddleware(lambda *_: None)

        response = self.make_request(middleware)

        self.assertIn((b"x-content-type-options", b"nosniff"), response[0]["headers"])
        self.assertIn((b"x-frame-options", b"DENY"), response[0]["headers"])

    def test_adds_content_security_policy_to_frontend(self) -> None:
        middleware = ApiProtectionMiddleware(lambda *_: None)

        response = self.make_request(middleware, path="/")

        self.assertIn(
            b"content-security-policy",
            {name for name, _ in response[0]["headers"]},
        )


if __name__ == "__main__":
    unittest.main()