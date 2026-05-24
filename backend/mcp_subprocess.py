import asyncio
import json
import sys
import uuid
from asyncio.subprocess import PIPE
from pathlib import Path


class AsyncMCPSubprocess:
    """Manage a MCP subprocess communicating over STDIO using NDJSON-framed messages.

    Notes:
    - Sends JSON lines to child stdin and expects JSON lines on stdout.
    - Correlates messages by `id` field.
    - Provides a simple streaming generator for responses.
    """

    def __init__(self, script_path: str | None = None):
        self.proc: asyncio.subprocess.Process | None = None
        self.stdout_task: asyncio.Task | None = None
        self.stderr_task: asyncio.Task | None = None
        self.pending: dict[str, asyncio.Future | asyncio.Queue] = {}
        self.script = script_path or str(Path(__file__).parent / "mcp_server_start.py")

    async def start(self) -> None:
        if self.proc is not None:
            return
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable,
            self.script,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        loop = asyncio.get_running_loop()
        self.stdout_task = loop.create_task(self._read_stdout())
        self.stderr_task = loop.create_task(self._read_stderr())
        # Perform JSON-RPC initialize handshake so the MCP server accepts requests
        init_id = uuid.uuid4().hex
        init_payload = {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "nanorag-backend", "version": "0.1"},
            },
        }
        # wait for initialize response
        fut = loop.create_future()
        self.pending[init_id] = fut
        line = json.dumps(init_payload, ensure_ascii=False) + "\n"
        try:
            sys.stderr.write("SEND: " + line)
            sys.stderr.flush()
        except Exception:
            pass
        self.proc.stdin.write(line.encode())
        await self.proc.stdin.drain()
        try:
            await asyncio.wait_for(fut, timeout=30.0)
            # send 'initialized' notification (no id)
            init_notify = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": None}
            try:
                sys.stderr.write("SEND: " + json.dumps(init_notify, ensure_ascii=False) + "\n")
                sys.stderr.flush()
            except Exception:
                pass
            self.proc.stdin.write((json.dumps(init_notify, ensure_ascii=False) + "\n").encode())
            await self.proc.stdin.drain()
        except Exception:
            # initialization failure will be visible in logs; continue anyway
            pass
        finally:
            self.pending.pop(init_id, None)

    async def stop(self) -> None:
        if self.proc is None:
            return
        try:
            self.proc.terminate()
        except ProcessLookupError:
            pass
        await self.proc.wait()
        if self.stdout_task:
            self.stdout_task.cancel()
        if self.stderr_task:
            self.stderr_task.cancel()
        self.proc = None

    async def _read_stdout(self) -> None:
        assert self.proc is not None
        reader = self.proc.stdout
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode().strip())
            except Exception:
                # ignore non-json lines
                continue
            rid = msg.get("id")
            if not rid:
                continue
            handler = self.pending.get(rid)
            if handler is None:
                continue
            if isinstance(handler, asyncio.Queue):
                await handler.put(msg)
            else:
                if not handler.done():
                    handler.set_result(msg)

    async def _read_stderr(self) -> None:
        assert self.proc is not None
        reader = self.proc.stderr
        while True:
            line = await reader.readline()
            if not line:
                break
            # forward subprocess stderr to parent's stderr for visibility
            sys.stderr.write(line.decode())

    async def call_tool(self, tool_name: str, params: dict | None = None, stream: bool = False, timeout: float = 30.0):
        """Invoke a tool exposed by the MCP subprocess.

        If stream is False returns a parsed JSON response (dict).
        If stream is True returns an async generator yielding NDJSON lines (strings).
        """
        if self.proc is None:
            raise RuntimeError("MCP subprocess is not running")

        request_id = uuid.uuid4().hex
        # Use JSON-RPC 2.0 style envelope expected by MCP stdio transport
        # MCP stdio expects higher-level JSON-RPC methods (e.g. 'tools/call')
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name},
        }
        if params is not None:
            # MCP expects tool call arguments under the 'arguments' key
            payload["params"]["arguments"] = params
        line = json.dumps(payload, ensure_ascii=False) + "\n"

        if stream:
            q: asyncio.Queue = asyncio.Queue()
            self.pending[request_id] = q
            # write request (log to stderr for visibility)
            try:
                sys.stderr.write("SEND: " + line)
                sys.stderr.flush()
            except Exception:
                pass
            self.proc.stdin.write(line.encode())
            await self.proc.stdin.drain()

            async def _gen():
                try:
                    while True:
                        msg = await q.get()
                        yield json.dumps(msg, ensure_ascii=False) + "\n"
                        # JSON-RPC stream finalizes with a 'result' or 'error' field
                        if "result" in msg or "error" in msg:
                            break
                finally:
                    self.pending.pop(request_id, None)

            return _gen()

        fut = asyncio.get_running_loop().create_future()
        self.pending[request_id] = fut
        try:
            sys.stderr.write("SEND: " + line)
            sys.stderr.flush()
        except Exception:
            pass
        self.proc.stdin.write(line.encode())
        await self.proc.stdin.drain()
        try:
            msg = await asyncio.wait_for(fut, timeout=timeout)
            # Return the JSON-RPC result when present, otherwise the full message
            return msg.get("result", msg)
        finally:
            self.pending.pop(request_id, None)
