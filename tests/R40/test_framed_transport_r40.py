from __future__ import annotations

import asyncio
import json

import pytest

from deployment.kex_canonical_stream_r40 import REQUEST_SCHEMA, build_tcp_server
from runtime.framed_json_r40 import decode_frame, encode_frame


def test_frame_codec_is_canonical_bounded_and_object_only():
    value = {"z": 1, "a": {"β": 2}}
    raw = encode_frame(value, max_frame_bytes=128)
    assert raw.endswith(b"\n")
    assert raw == (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    assert decode_frame(raw, max_frame_bytes=128) == value
    with pytest.raises(ValueError, match="FRAME_TOO_LARGE"):
        encode_frame({"payload": "x" * 256}, max_frame_bytes=64)
    with pytest.raises(ValueError, match="FRAME_OBJECT_REQUIRED"):
        decode_frame(b"[]\n", max_frame_bytes=64)
    with pytest.raises(ValueError, match="FRAME_TERMINATOR_REQUIRED"):
        decode_frame(b"{}", max_frame_bytes=64)


def test_non_loopback_tcp_requires_projection_auth(tmp_path):
    async def run():
        with pytest.raises(ValueError, match="NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN"):
            await build_tcp_server(tmp_path / "state", host="0.0.0.0", port=0, auth_token=None)
    asyncio.run(run())


def test_async_stream_auth_ping_and_same_canonical_dispatch(tmp_path):
    async def run():
        server = await build_tcp_server(
            tmp_path / "state",
            host="127.0.0.1",
            port=0,
            auth_token="frame-secret",
            max_frame_bytes=4096,
        )
        seen = []
        original = server.host_runtime.canonical_execute  # type: ignore[attr-defined]

        def capture(command):
            seen.append(command)
            return {"status": "EXECUTED_LOCAL_VERIFIED", "command": command}

        server.host_runtime.canonical_execute = capture  # type: ignore[attr-defined]
        try:
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=4097)
            writer.write(encode_frame({
                "schema": REQUEST_SCHEMA,
                "request_id": "unauthorized",
                "type": "canonical.ping",
            }, max_frame_bytes=4096))
            await writer.drain()
            unauthorized = decode_frame(await reader.readline(), max_frame_bytes=4096)
            assert unauthorized["status"] == "BLOCKED:UNAUTHORIZED"
            writer.close(); await writer.wait_closed()

            reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=4097)
            writer.write(encode_frame({
                "schema": REQUEST_SCHEMA,
                "request_id": "ping-1",
                "type": "canonical.ping",
                "authorization": "Bearer frame-secret",
            }, max_frame_bytes=4096))
            await writer.drain()
            ping = decode_frame(await reader.readline(), max_frame_bytes=4096)
            assert ping["status"] == "PASS"

            command = {"source": "test://framed", "data_class": "CORRECTION", "payload": {"x": 1}}
            writer.write(encode_frame({
                "schema": REQUEST_SCHEMA,
                "request_id": "execute-1",
                "type": "canonical.execute",
                "authorization": "Bearer frame-secret",
                "command": command,
            }, max_frame_bytes=4096))
            await writer.drain()
            executed = decode_frame(await reader.readline(), max_frame_bytes=4096)
            assert executed["status"] == "EXECUTED_LOCAL_VERIFIED"
            assert seen == [command]
            writer.close(); await writer.wait_closed()
        finally:
            server.host_runtime.canonical_execute = original  # type: ignore[attr-defined]
            server.close()
            await server.wait_closed()
    asyncio.run(run())


def test_async_stream_rejects_oversized_frame_and_closes_connection(tmp_path):
    async def run():
        server = await build_tcp_server(
            tmp_path / "state",
            host="127.0.0.1",
            port=0,
            max_frame_bytes=256,
        )
        try:
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=4096)
            writer.write(b'{"payload":"' + (b"x" * 400) + b'"}\n')
            await writer.drain()
            response = decode_frame(await reader.readline(), max_frame_bytes=256)
            assert response["status"] == "BLOCKED:INVALID_FRAME"
            assert "FRAME_" in response["reason"]
            assert await reader.read() == b""
            writer.close(); await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()
    asyncio.run(run())
