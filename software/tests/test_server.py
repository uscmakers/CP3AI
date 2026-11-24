"""
End-to-end tests for the table server: real WebSocket clients
talking to a server on a random local port, with a fake gantry.

    cd software && python3 -m unittest discover -s tests -v
"""

import asyncio
import base64
import json
import os
import struct
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game_engine import GameEngine  # noqa: E402
from gantry import GantryError  # noqa: E402
from server import TableServer  # noqa: E402


class FakeGantry:
    """Records moves. Can be slowed down, or told to fail."""

    def __init__(self, delay=0.0):
        self.delay = delay
        self.moves = []
        self.fail_on_move = None
        self.release = threading.Event()
        self.release.set()

    def move(self, step):
        self.release.wait(5)
        if self.fail_on_move is not None and len(self.moves) == self.fail_on_move:
            raise GantryError("motor stalled")
        self.moves.append(step)
        if self.delay:
            threading.Event().wait(self.delay)


class Client:
    """Minimal WebSocket client (masked frames, as clients must send)."""

    @classmethod
    async def connect(cls, port):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        key = base64.b64encode(os.urandom(16)).decode()
        writer.write(
            f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode()
        )
        response = await reader.readuntil(b"\r\n\r\n")
        assert response.startswith(b"HTTP/1.1 101"), response
        return cls(reader, writer)

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def send_raw(self, text, opcode=0x1):
        payload = text.encode()
        mask = os.urandom(4)
        n = len(payload)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([0x80 | n])
        else:
            header += bytes([0x80 | 126]) + struct.pack("!H", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.writer.write(header + mask + masked)
        await self.writer.drain()

    async def send(self, message):
        await self.send_raw(json.dumps(message))

    async def recv(self, timeout=10):
        async def read():
            while True:
                first, second = await self.reader.readexactly(2)
                length = second & 0x7F
                if length == 126:
                    (length,) = struct.unpack("!H", await self.reader.readexactly(2))
                elif length == 127:
                    (length,) = struct.unpack("!Q", await self.reader.readexactly(8))
                data = await self.reader.readexactly(length)
                if first & 0x0F == 0x1:
                    return json.loads(data)
                if first & 0x0F == 0x8:
                    return {"type": "closed"}

        return await asyncio.wait_for(read(), timeout)

    async def recv_until(self, predicate, timeout=20):
        """Messages until one matches predicate; returns (match, earlier)."""
        seen = []
        while True:
            message = await self.recv(timeout)
            if predicate(message):
                return message, seen
            seen.append(message)

    async def close(self):
        self.writer.close()


def idle_state(message):
    return message["type"] == "state" and not message["busy"]


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gantry = FakeGantry()
        self.engine = GameEngine(start_formation="triangle_6")
        self.server = TableServer(self.engine, self.gantry, min_confidence=0.5)
        self.listener = await asyncio.start_server(
            self.server.handle_connection, "127.0.0.1", 0
        )
        self.port = self.listener.sockets[0].getsockname()[1]
        self.clients = []

    async def asyncTearDown(self):
        self.gantry.release.set()
        for client in self.clients:
            await client.close()
        self.listener.close()
        await self.listener.wait_closed()

    async def connect(self):
        client = await Client.connect(self.port)
        self.clients.append(client)
        state = await client.recv()
        return client, state

    async def test_new_client_gets_state_with_spots(self):
        _, state = await self.connect()

        self.assertEqual(state["type"], "state")
        self.assertEqual(state["formation"], "triangle_6")
        self.assertEqual(state["remaining"], 6)
        self.assertFalse(state["busy"])
        self.assertEqual(len(state["spots"]), 6)
        self.assertEqual(
            sorted(spot["cup_id"] for spot in state["spots"]),
            list(range(6)),
        )

    async def test_cup_hit_by_id_parks_cup_and_broadcasts(self):
        client, _ = await self.connect()
        watcher, _ = await self.connect()

        await client.send({"type": "cup_hit", "cup_id": 0})

        busy = await client.recv()
        self.assertTrue(busy["busy"])
        state, _ = await client.recv_until(idle_state)

        self.assertEqual(state["remaining"], 5)
        parked = [cup for cup in state["cups"] if cup["status"] == "parked"]
        self.assertEqual([cup["id"] for cup in parked], [0])
        self.assertIsNotNone(parked[0]["slot_id"])
        # The hit cup's spot is still listed, so the app can draw an outline.
        self.assertIn(0, [spot["cup_id"] for spot in state["spots"]])
        self.assertEqual(state["rearrange_option"], "backpack_kid_5")
        self.assertGreaterEqual(len(self.gantry.moves), 1)

        # Other clients see the same result.
        watched, _ = await watcher.recv_until(idle_state)
        self.assertEqual(watched["remaining"], 5)

    async def test_cv_hit_by_position(self):
        client, state = await self.connect()
        target = next(cup for cup in state["cups"] if cup["id"] == 4)

        await client.send({
            "type": "cup_hit",
            "x_mm": target["x_mm"] + 10,
            "y_mm": target["y_mm"] - 5,
            "confidence": 0.9,
        })
        state, _ = await client.recv_until(idle_state)

        parked = [cup["id"] for cup in state["cups"] if cup["status"] == "parked"]
        self.assertEqual(parked, [4])

    async def test_cv_hit_with_no_cup_there(self):
        client, _ = await self.connect()

        await client.send({"type": "cup_hit", "x_mm": 5, "y_mm": 1100})
        reply = await client.recv()

        self.assertEqual(reply["type"], "error")
        self.assertIn("No cup in play", reply["message"])
        self.assertEqual(self.gantry.moves, [])

    async def test_low_confidence_hit_is_ignored(self):
        client, state = await self.connect()
        cup = state["cups"][0]

        await client.send({
            "type": "cup_hit", "x_mm": cup["x_mm"], "y_mm": cup["y_mm"], "confidence": 0.2,
        })
        reply = await client.recv()

        self.assertEqual(reply["type"], "error")
        self.assertIn("confidence", reply["message"])
        self.assertEqual(self.engine.snapshot()["remaining"], 6)

    async def test_commands_rejected_while_gantry_moves(self):
        client, state = await self.connect()
        self.gantry.release.clear()  # hold the gantry mid-move

        await client.send({"type": "cup_hit", "cup_id": 0})
        busy = await client.recv()
        self.assertTrue(busy["busy"])

        # A camera hit and an app command arriving now are both refused.
        cup = next(c for c in state["cups"] if c["id"] == 2)
        await client.send({"type": "cup_hit", "x_mm": cup["x_mm"], "y_mm": cup["y_mm"]})
        reply = await client.recv()
        self.assertEqual(reply["type"], "error")
        self.assertIn("Gantry is moving", reply["message"])

        await client.send({"type": "reset"})
        reply = await client.recv()
        self.assertIn("Gantry is moving", reply["message"])

        # get_state still answers, showing busy.
        await client.send({"type": "get_state"})
        reply = await client.recv()
        self.assertTrue(reply["busy"])

        self.gantry.release.set()
        state, _ = await client.recv_until(idle_state)
        self.assertEqual(state["remaining"], 5)

    async def test_rearrangement(self):
        client, _ = await self.connect()

        await client.send({"type": "cup_hit", "cup_id": 0})
        await client.recv_until(idle_state)

        await client.send({"type": "rearrange", "formation": "triangle_3"})
        reply = await client.recv()
        self.assertEqual(reply["type"], "error")

        await client.send({"type": "rearrange", "formation": "backpack_kid_5"})
        state, _ = await client.recv_until(idle_state)

        self.assertEqual(state["formation"], "backpack_kid_5")
        self.assertEqual(state["rearrangements_left"], 0)
        self.assertIsNone(state["rearrange_option"])
        active = {cup["id"] for cup in state["cups"] if cup["status"] == "active"}
        self.assertEqual({spot["cup_id"] for spot in state["spots"]}, active)

    async def test_gantry_failure_is_reported(self):
        client, _ = await self.connect()
        watcher, _ = await self.connect()
        self.gantry.fail_on_move = 0

        await client.send({"type": "cup_hit", "cup_id": 0})
        error, _ = await client.recv_until(lambda m: m["type"] == "error")
        self.assertIn("gantry stopped", error["message"])

        state, _ = await client.recv_until(idle_state)
        self.assertEqual(state["remaining"], 6)  # cup 0 recorded back in place
        watched, _ = await watcher.recv_until(lambda m: m["type"] == "error")
        self.assertIn("motor stalled", watched["message"])

        # The table keeps working afterwards.
        self.gantry.fail_on_move = None
        await client.send({"type": "cup_hit", "cup_id": 0})
        state, _ = await client.recv_until(idle_state)
        self.assertEqual(state["remaining"], 5)

    async def test_reset(self):
        client, _ = await self.connect()
        await client.send({"type": "cup_hit", "cup_id": 0})
        await client.recv_until(idle_state)

        await client.send({"type": "reset", "start_formation": "triangle_10"})
        state, _ = await client.recv_until(idle_state)

        self.assertEqual(state["formation"], "triangle_10")
        self.assertEqual(state["remaining"], 10)
        self.assertFalse(state["game_started"])

    async def test_bad_messages(self):
        client, _ = await self.connect()

        for text, expected in [
            ("not json", "must be JSON"),
            ("[1, 2]", "JSON objects"),
            ('{"type": "launch"}', "Unknown message type"),
            ('{"type": "cup_hit"}', "needs cup_id"),
            ('{"type": "cup_hit", "cup_id": "3"}', "must be an integer"),
            ('{"type": "cup_hit", "cup_id": 42}', "not in play"),
            ('{"type": "reset", "start_formation": "vertical_2"}', "start_formation"),
        ]:
            await client.send_raw(text)
            reply = await client.recv()
            self.assertEqual(reply["type"], "error", text)
            self.assertIn(expected, reply["message"], text)

    async def test_plain_http_request_is_refused(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        response = await reader.read()
        writer.close()
        self.assertTrue(response.startswith(b"HTTP/1.1 426"))


if __name__ == "__main__":
    unittest.main()
