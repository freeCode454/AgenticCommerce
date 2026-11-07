import asyncio
from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest

from app.models.asset import Asset
from app.services import media_archive


@pytest.mark.parametrize("source", [
    "http://sample.oss-cn-shanghai.aliyuncs.com/file",
    "https://sample.oss-cn-shanghai.aliyuncs.com.attacker.example/file",
    "https://user@sample.oss-cn-shanghai.aliyuncs.com/file",
    "https://sample.oss-cn-shanghai.aliyuncs.com:8443/file",
    "https://127.0.0.1/file",
])
async def test_archive_rejects_untrusted_source_before_dns(monkeypatch, source):
    resolve = AsyncMock()
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(media_archive.ArchiveError):
        await media_archive.source_request(source)
    resolve.assert_not_awaited()


async def test_archive_pins_public_address_and_preserves_signature(monkeypatch):
    address = [(None, None, None, None, ("8.8.8.8", 443))]
    resolve = AsyncMock(return_value=address)
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    host = "sample.oss-cn-shanghai.aliyuncs.com"
    source = f"https://{host}/file?signature=a%2Fb%3D"
    url, tls_host = await media_archive.source_request(source)
    assert url.host == "8.8.8.8" and tls_host == host
    assert url.raw_path == b"/file?signature=a%2Fb%3D"
    address.append((None, None, None, None, ("127.0.0.1", 443)))
    with pytest.raises(media_archive.ArchiveError):
        await media_archive.source_request(source)


@pytest.mark.parametrize(("status", "retryable"), [(200, None), (302, False), (503, True)])
async def test_archive_download_uses_original_tls_host_and_does_not_follow_redirects(monkeypatch, status, retryable):
    address = [(None, None, None, None, ("8.8.8.8", 443))]
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=address))
    host = "sample.oss-cn-shanghai.aliyuncs.com"
    data = b"\x89PNG\r\n\x1a\n" + b"test-fixture"
    seen = []

    def respond(request):
        seen.append(request)
        assert request.url.host == "8.8.8.8"
        assert request.headers["Host"] == request.extensions["sni_hostname"] == host
        return httpx.Response(status, headers={"Location": "https://127.0.0.1/file"},
                              stream=httpx.ByteStream(data))

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(respond))
    file = BytesIO()
    source = f"https://{host}/file?signature=test"
    if retryable is None:
        assert await media_archive.fetch_source(source, "image", file) == (len(data), "image/png")
        assert file.read() == data
    else:
        with pytest.raises(media_archive.ArchiveError) as error:
            await media_archive.fetch_source(source, "image", file)
        assert error.value.retryable is retryable
    assert len(seen) == 1


async def test_archive_recovers_uploaded_object_after_database_interruption(monkeypatch):
    fetch = AsyncMock()
    monkeypatch.setattr(media_archive, "fetch_source", fetch)
    monkeypatch.setattr(media_archive, "existing_object", lambda key: (100, "image/png"))
    asset = Asset(id="asset", tenant_id="tenant", type="image", url="https://expired.example.test")
    await media_archive.store_asset(asset)
    assert asset.archive_status == "stored" and asset.archive_size == 100
    assert asset.display_url == "/api/v1/assets/asset/file"
    fetch.assert_not_awaited()
