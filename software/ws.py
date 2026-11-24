"""
Minimal WebSocket server side (RFC 6455) on asyncio streams.

Standard library only, so the table server runs on the UNO Q with no
packages to install. Supports what the table protocol needs: text
messages (including fragmented ones), ping/pong, and close.
"""

import asyncio
import base64
import hashlib
import struct

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MAX_MESSAGE_BYTES = 1 << 20
SEND_TIMEOUT_S = 5

OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class WebSocketError(Exception):
    """The peer broke the protocol; the connection is closed."""


class Connection:
    """One accepted WebSocket connection."""

    def __init__(self, reader, writer):
        self._reader = reader
        self._writer = writer
        self.closed = False
        peer = writer.get_extra_info("peername")
        self.peer = f"{peer[0]}:{peer[1]}" if peer else "unknown"

    async def recv(self):
        """
        Next text message, or None once the peer has closed the
        connection. Answers pings while waiting.
        """

        parts = []
        size = 0

        while True:
            try:
                fin, opcode, payload = await self._read_frame()
            except (asyncio.IncompleteReadError, ConnectionError, OSError):
                self.closed = True
                return None

            if opcode == OP_CLOSE:
                await self._send_frame(OP_CLOSE, payload[:2])
                await self.close()
                return None

            if opcode == OP_PING:
                await self._send_frame(OP_PONG, payload)
                continue

            if opcode == OP_PONG:
                continue

            if opcode == OP_BINARY:
                await self.close(1003)
                raise WebSocketError("Binary messages are not supported")

            if opcode == OP_TEXT and parts:
                await self.close(1002)
                raise WebSocketError("New message before the last one ended")

            if opcode == OP_CONTINUATION and not parts:
                await self.close(1002)
                raise WebSocketError("Continuation frame with no message")

            if opcode not in (OP_TEXT, OP_CONTINUATION):
                await self.close(1002)
                raise WebSocketError(f"Unknown opcode {opcode}")

            size += len(payload)
            if size > MAX_MESSAGE_BYTES:
                await self.close(1009)
                raise WebSocketError("Message too large")

            parts.append(payload)

            if fin:
                try:
                    return b"".join(parts).decode("utf-8")
                except UnicodeDecodeError:
                    await self.close(1007)
                    raise WebSocketError("Message is not valid UTF-8")

    async def send(self, text):
        """Send a text message. Raises ConnectionError if the peer is gone."""

        await self._send_frame(OP_TEXT, text.encode("utf-8"))

    async def close(self, code=1000):
        if self.closed:
            return
        self.closed = True
        try:
            await self._send_frame(OP_CLOSE, struct.pack("!H", code), force=True)
        except (ConnectionError, OSError, asyncio.TimeoutError):
            pass
        self._writer.close()

    async def _read_frame(self):
        first, second = await self._reader.readexactly(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = second & 0x80
        length = second & 0x7F

        if length == 126:
            (length,) = struct.unpack("!H", await self._reader.readexactly(2))
        elif length == 127:
            (length,) = struct.unpack("!Q", await self._reader.readexactly(8))

        if opcode >= OP_CLOSE and (length > 125 or not fin):
            await self.close(1002)
            raise WebSocketError("Bad control frame")

        if not masked:
            await self.close(1002)
            raise WebSocketError("Client frames must be masked")

        if length > MAX_MESSAGE_BYTES:
            await self.close(1009)
            raise WebSocketError("Message too large")

        mask = await self._reader.readexactly(4)
        data = await self._reader.readexactly(length)
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        return fin, opcode, payload

    async def _send_frame(self, opcode, payload, force=False):
        if self.closed and not force:
            raise ConnectionError("WebSocket is closed")

        n = len(payload)
        if n < 126:
            header = struct.pack("!BB", 0x80 | opcode, n)
        elif n < 65536:
            header = struct.pack("!BBH", 0x80 | opcode, 126, n)
        else:
            header = struct.pack("!BBQ", 0x80 | opcode, 127, n)

        # One write per frame, so frames from concurrent senders never interleave.
        self._writer.write(header + payload)
        await asyncio.wait_for(self._writer.drain(), SEND_TIMEOUT_S)


async def accept(reader, writer):
    """
    Complete the WebSocket handshake. Returns a Connection, or None
    (after answering with an HTTP error) if the request isn't one.
    """

    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError,
            asyncio.TimeoutError, ConnectionError, OSError):
        writer.close()
        return None

    lines = request.decode("latin-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()

    key = headers.get("sec-websocket-key")
    is_websocket = (
        lines[0].startswith("GET ")
        and "websocket" in headers.get("upgrade", "").lower()
        and "upgrade" in headers.get("connection", "").lower()
        and headers.get("sec-websocket-version") == "13"
        and key
    )

    if not is_websocket:
        body = b"This is the cup pong table's WebSocket server.\n"
        writer.write(
            b"HTTP/1.1 426 Upgrade Required\r\n"
            b"Upgrade: websocket\r\nSec-WebSocket-Version: 13\r\n"
            b"Content-Type: text/plain\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )
        try:
            await writer.drain()
        finally:
            writer.close()
        return None

    accept_key = base64.b64encode(
        hashlib.sha1((key + GUID).encode()).digest()
    ).decode()

    writer.write(
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n".encode()
    )
    await writer.drain()
    return Connection(reader, writer)
