from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import asyncio
import os

from deployment.kex_runtime_service_r40 import CanonicalRuntimeHost
from runtime.framed_json_r40 import DEFAULT_MAX_FRAME_BYTES, FRAME_SCHEMA, read_frame, write_frame


REQUEST_SCHEMA = "braink.canonical-stream.r40/v1"


class CanonicalStreamProjectionR40:
    """Async framed projection over the canonical R40 execution graph.

    This class performs transport authentication and framing only. DATA classing,
    BRAINK operator authority, capability resolution, IL-LLM dispatch, node/VFS
    mutation, proof, mesh and promotion remain owned by CanonicalExecutionR40.
    """

    def __init__(self, host_runtime: CanonicalRuntimeHost, *, auth_token: str | None, max_frame_bytes: int):
        self.host_runtime = host_runtime
        self.auth_token = auth_token
        self.max_frame_bytes = int(max_frame_bytes)
        if self.max_frame_bytes <= 0:
            raise ValueError("FRAME_LIMIT_INVALID")

    def _authorized(self, envelope: dict[str, Any]) -> bool:
        if not self.auth_token:
            return True
        return envelope.get("authorization") == "Bearer " + self.auth_token

    def dispatch(self, envelope: dict[str, Any]) -> dict[str, Any]:
        request_id = str(envelope.get("request_id", ""))
        if envelope.get("schema") != REQUEST_SCHEMA:
            return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": "BLOCKED:FRAME_SCHEMA"}
        if not self._authorized(envelope):
            return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": "BLOCKED:UNAUTHORIZED"}
        message_type = envelope.get("type")
        if message_type == "canonical.ping":
            return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": "PASS", "result": {"runtime": "KEDDEH-KEX-R40"}}
        if message_type == "canonical.status":
            return {
                "schema": FRAME_SCHEMA,
                "request_id": request_id,
                "status": "READ",
                "result": {
                    "runtime": self.host_runtime.ready(),
                    "global_illlm": self.host_runtime.canonical.global_knowledge.snapshot(),
                    "scheduler": self.host_runtime.canonical.scheduler.snapshot(),
                    "fabric": self.host_runtime.fabric_node.identity(),
                },
            }
        if message_type == "canonical.execute":
            command = envelope.get("command")
            if not isinstance(command, dict):
                return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": "BLOCKED:INVALID_COMMAND"}
            result = self.host_runtime.canonical_execute(command)
            return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": result.get("status", "FAILED:CANONICAL_EXECUTION"), "result": result}
        return {"schema": FRAME_SCHEMA, "request_id": request_id, "status": "BLOCKED:UNKNOWN_FRAME_TYPE"}

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                try:
                    envelope = await read_frame(reader, max_frame_bytes=self.max_frame_bytes)
                except EOFError:
                    break
                except ValueError as exc:
                    await write_frame(
                        writer,
                        {"schema": FRAME_SCHEMA, "request_id": "", "status": "BLOCKED:INVALID_FRAME", "reason": str(exc)},
                        max_frame_bytes=self.max_frame_bytes,
                    )
                    break
                try:
                    response = self.dispatch(envelope)
                except (KeyError, ValueError) as exc:
                    response = {"schema": FRAME_SCHEMA, "request_id": str(envelope.get("request_id", "")), "status": "BLOCKED:INVALID_COMMAND", "reason": str(exc)}
                except Exception as exc:
                    response = {"schema": FRAME_SCHEMA, "request_id": str(envelope.get("request_id", "")), "status": "FAILED:CANONICAL_EXECUTION", "reason": type(exc).__name__ + ":" + str(exc)}
                await write_frame(writer, response, max_frame_bytes=self.max_frame_bytes)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def build_tcp_server(
    state_root: str | Path,
    *,
    computer_id: str = "A",
    host: str = "127.0.0.1",
    port: int = 8812,
    auth_token: str | None = None,
    advertised_endpoint: str | None = None,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> asyncio.AbstractServer:
    if host not in {"127.0.0.1", "::1", "localhost"} and not auth_token:
        raise ValueError("NON_LOOPBACK_BIND_REQUIRES_AUTH_TOKEN")
    runtime = CanonicalRuntimeHost(state_root, computer_id, advertised_endpoint=advertised_endpoint)
    projection = CanonicalStreamProjectionR40(runtime, auth_token=auth_token, max_frame_bytes=max_frame_bytes)
    server = await asyncio.start_server(
        projection.handle,
        host=host,
        port=int(port),
        limit=int(max_frame_bytes) + 1,
    )
    # Attach readback handles for tests/operator inspection without introducing a
    # separate runtime authority.
    server.host_runtime = runtime  # type: ignore[attr-defined]
    server.projection = projection  # type: ignore[attr-defined]
    return server


async def build_unix_server(
    state_root: str | Path,
    *,
    socket_path: str | Path,
    computer_id: str = "A",
    auth_token: str | None = None,
    advertised_endpoint: str | None = None,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> asyncio.AbstractServer:
    socket_path = Path(socket_path)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass
    runtime = CanonicalRuntimeHost(state_root, computer_id, advertised_endpoint=advertised_endpoint)
    projection = CanonicalStreamProjectionR40(runtime, auth_token=auth_token, max_frame_bytes=max_frame_bytes)
    server = await asyncio.start_unix_server(
        projection.handle,
        path=str(socket_path),
        limit=int(max_frame_bytes) + 1,
    )
    os.chmod(socket_path, 0o660)
    server.host_runtime = runtime  # type: ignore[attr-defined]
    server.projection = projection  # type: ignore[attr-defined]
    return server


async def _main_async(args) -> None:
    token = os.environ.get(args.auth_token_env)
    if args.unix_socket:
        server = await build_unix_server(
            args.state_root,
            socket_path=args.unix_socket,
            computer_id=args.computer_id,
            auth_token=token,
            advertised_endpoint=args.advertised_endpoint,
            max_frame_bytes=args.max_frame_bytes,
        )
    else:
        server = await build_tcp_server(
            args.state_root,
            computer_id=args.computer_id,
            host=args.host,
            port=args.port,
            auth_token=token,
            advertised_endpoint=args.advertised_endpoint,
            max_frame_bytes=args.max_frame_bytes,
        )
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--computer-id", default="A")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8812)
    parser.add_argument("--unix-socket")
    parser.add_argument("--auth-token-env", default="KEX_AUTH_TOKEN")
    parser.add_argument("--advertised-endpoint", default=os.environ.get("BRAINK_ADVERTISED_ENDPOINT"))
    parser.add_argument("--max-frame-bytes", type=int, default=int(os.environ.get("BRAINK_MAX_FRAME_BYTES", str(DEFAULT_MAX_FRAME_BYTES))))
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
