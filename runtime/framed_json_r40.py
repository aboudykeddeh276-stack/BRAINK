from __future__ import annotations

from typing import Any
import asyncio
import json


FRAME_SCHEMA = "braink.frame.r40/v1"
DEFAULT_MAX_FRAME_BYTES = 1024 * 1024


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def encode_frame(value: dict[str, Any], *, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes:
    if not isinstance(value, dict):
        raise ValueError("FRAME_OBJECT_REQUIRED")
    if int(max_frame_bytes) <= 0:
        raise ValueError("FRAME_LIMIT_INVALID")
    raw = (canonical_json(value) + "\n").encode("utf-8")
    if len(raw) > int(max_frame_bytes):
        raise ValueError(f"FRAME_TOO_LARGE:{len(raw)}>{int(max_frame_bytes)}")
    return raw


def decode_frame(raw: bytes, *, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> dict[str, Any]:
    if int(max_frame_bytes) <= 0:
        raise ValueError("FRAME_LIMIT_INVALID")
    if not raw:
        raise ValueError("FRAME_EMPTY")
    if len(raw) > int(max_frame_bytes):
        raise ValueError(f"FRAME_TOO_LARGE:{len(raw)}>{int(max_frame_bytes)}")
    if not raw.endswith(b"\n"):
        raise ValueError("FRAME_TERMINATOR_REQUIRED")
    try:
        value = json.loads(raw[:-1].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("FRAME_UTF8_INVALID") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("FRAME_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("FRAME_OBJECT_REQUIRED")
    return value


async def read_frame(reader: asyncio.StreamReader, *, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> dict[str, Any]:
    if int(max_frame_bytes) <= 0:
        raise ValueError("FRAME_LIMIT_INVALID")
    try:
        raw = await reader.readuntil(b"\n")
    except asyncio.LimitOverrunError as exc:
        # The StreamReader was constructed with a bounded limit. Do not continue
        # parsing a connection after the framing boundary has been exceeded.
        raise ValueError("FRAME_LIMIT_EXCEEDED") from exc
    except asyncio.IncompleteReadError as exc:
        if exc.partial:
            raise ValueError("FRAME_TRUNCATED") from exc
        raise EOFError("FRAME_EOF") from exc
    return decode_frame(raw, max_frame_bytes=max_frame_bytes)


async def write_frame(writer: asyncio.StreamWriter, value: dict[str, Any], *, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> None:
    writer.write(encode_frame(value, max_frame_bytes=max_frame_bytes))
    await writer.drain()
