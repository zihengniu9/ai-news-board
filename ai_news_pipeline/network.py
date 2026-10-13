from __future__ import annotations

import json
import os
import socket
import urllib.request
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import urlparse


def configure_process_proxy(proxy_url: str) -> None:
    """Make third-party HTTP clients inherit the verified project proxy."""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ[key] = proxy_url
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"


def verify_proxy_listener(proxy_url: str, timeout: float = 3.0) -> dict[str, object]:
    parsed = urlparse(proxy_url)
    if not parsed.hostname or not parsed.port:
        raise ValueError("代理 URL 缺少主机或端口")
    with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout):
        return {"host": parsed.hostname, "port": parsed.port, "listening": True}


def build_url_opener(proxy_url: str) -> urllib.request.OpenerDirector:
    handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    return urllib.request.build_opener(handler)


def verify_https_exit(proxy_url: str, check_url: str, timeout: float = 15.0) -> dict[str, object]:
    opener = build_url_opener(proxy_url)
    request = urllib.request.Request(
        check_url,
        headers={"User-Agent": "ai-news-pipeline/0.1 proxy-check"},
    )
    with opener.open(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", "replace")
        try:
            payload: object = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw[:200]
        return {
            "status": response.status,
            "url": response.geturl(),
            "payload": payload,
        }


@contextmanager
def requests_session(proxy_url: str) -> Iterator[object]:
    import requests

    session = requests.Session()
    session.proxies.update({"http": proxy_url, "https": proxy_url})
    try:
        yield session
    finally:
        session.close()

