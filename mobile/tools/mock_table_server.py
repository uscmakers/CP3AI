"""
Stand-in for the table server, for trying the iOS app without the gantry.

Speaks docs/websocket-protocol.md. No movement planning: a hit cup
goes straight to a parking slot after a short "moving" delay, and a
rearrangement pairs cups with the new spots row by row. Standard
library only.

    python3 mock_table_server.py              # listens on port 8765
    python3 mock_table_server.py --start triangle_6 --move-seconds 0.5

Type commands into this terminal to act as the camera:

    hit 3          camera saw a hit in cup 3
    rearrange      rearrange into the offered formation
    reset          re-rack
    state          print the current state
"""

import argparse
import asyncio
import base64
import hashlib
import json
import math
import struct
import sys

D = 92.0
H = math.sqrt(3) / 2
WORKSPACE_WIDTH = 810
BACK_CLEARANCE = 40
PORT = 8765

# Offsets in cup diameters, as in software/layouts.py.
LAYOUTS = {
    "triangle_10": [(-1.5, 0), (-0.5, 0), (0.5, 0), (1.5, 0),
                    (-1, H), (0, H), (1, H),
                    (-0.5, 2 * H), (0.5, 2 * H), (0, 3 * H)],
    "triangle_6": [(-1, 0), (0, 0), (1, 0), (-0.5, H), (0.5, H), (0, 2 * H)],
    "backpack_kid_5": [(0, 0), (0, 1), (0, 2), (H, 0.5), (H, 1.5)],
    "triangle_3": [(-0.5, 0), (0.5, 0), (0, H)],
    "vertical_2": [(0, 0), (0, 1)],
}
REARRANGE_FORMATIONS = {6: "triangle_6", 5: "backpack_kid_5", 3: "triangle_3", 2: "vertical_2"}
SLOTS = [f"{side}{n}" for side in "LR" for n in range(1, 6)]


def place(name):
    offsets = LAYOUTS[name]
    xs = [dx for dx, _ in offsets]
    center_x = (min(xs) + max(xs)) / 2
    min_y = min(dy for _, dy in offsets)
    return [
        (WORKSPACE_WIDTH / 2 + (dx - center_x) * D, BACK_CLEARANCE + D / 2 + (dy - min_y) * D)
        for dx, dy in offsets
    ]


def slot_position(slot):
    side, n = slot[0], int(slot[1:])
    x = D / 2 + 15 if side == "L" else WORKSPACE_WIDTH - D / 2 - 15
    return (x, D / 2 + 15 + (n - 1) * (D + 10))


class Game:
    def __init__(self, start):
        self.start = start
        self.move_seconds = 1.0
        self.reset()

    def reset(self):
        self.formation = self.start
        self.spots = place(self.formation)
        self.spot_cup = list(range(len(self.spots)))  # spot index -> cup id
        self.active = {i: p for i, p in enumerate(self.spots)}
        self.parked = {}  # cup id -> slot
        self.rearrangements_left = 1
        self.started = False
        self.busy = False
        self.version = getattr(self, "version", 0) + 1

    @property
    def option(self):
        if self.rearrangements_left <= 0:
            return None
        option = REARRANGE_FORMATIONS.get(len(self.active))
        return None if option == self.formation else option

    def snapshot(self):
        r = lambda v: round(v, 2)
        cups = [{"id": i, "status": "active", "formation_index": self.spot_cup.index(i) if i in self.spot_cup else None,
                 "x_mm": r(x), "y_mm": r(y)} for i, (x, y) in sorted(self.active.items())]
        cups += [{"id": i, "status": "parked", "slot_id": s,
                  "x_mm": r(slot_position(s)[0]), "y_mm": r(slot_position(s)[1])} for i, s in sorted(self.parked.items())]
        return {
            "type": "state", "version": self.version, "formation": self.formation,
            "start_formation": self.start, "game_started": self.started, "busy": self.busy,
            "remaining": len(self.active), "rearrangements_left": self.rearrangements_left,
            "rearrange_option": self.option, "cup_diameter_mm": D,
            "gantry": {"x_mm": 405.0, "y_mm": 600.0},
            "cups": cups,
            "spots": [{"index": i, "x_mm": r(x), "y_mm": r(y), "cup_id": self.spot_cup[i]}
                      for i, (x, y) in enumerate(self.spots)],
        }


class Server:
    def __init__(self, game):
        self.game = game
        self.clients = set()

    async def broadcast(self):
        message = json.dumps(self.game.snapshot())
        for writer in list(self.clients):
            try:
                await send_text(writer, message)
            except (ConnectionError, OSError):
                self.clients.discard(writer)

    async def command(self, message, reply):
        game = self.game
        kind = message.get("type")
        if kind == "get_state":
            await reply(json.dumps(game.snapshot()))
            return
        if game.busy:
            await reply(error("Gantry is moving; try again when it stops"))
            return

        if kind == "cup_hit":
            cup = message.get("cup_id")
            if cup not in game.active:
                await reply(error(f"Cup {cup} is not in play"))
                return
            await self.move(lambda: self.park(cup))
        elif kind == "rearrange":
            option = game.option
            if option is None:
                await reply(error(f"No rearrangement offered for {len(game.active)} cups"))
                return
            if message.get("formation") not in (None, option):
                await reply(error(f"{message.get('formation')} is not offered; the option is {option}"))
                return
            await self.move(lambda: self.rearrange(option), seconds=2 * game.move_seconds)
        elif kind == "reset":
            game.reset()
            await self.broadcast()
        else:
            await reply(error(f"Unknown command: {kind}"))

    async def move(self, finish, seconds=None):
        self.game.busy = True
        self.game.version += 1
        await self.broadcast()
        await asyncio.sleep(self.game.move_seconds if seconds is None else seconds)
        finish()
        self.game.busy = False
        self.game.started = True
        self.game.version += 1
        await self.broadcast()

    def park(self, cup):
        game = self.game
        game.active.pop(cup)
        game.parked[cup] = next(s for s in SLOTS if s not in game.parked.values())
        print(f"parked cup {cup} in {game.parked[cup]}")

    def rearrange(self, option):
        game = self.game
        row = lambda p: (round(p[1], 1), p[0])
        cups = sorted(game.active, key=lambda c: row(game.active[c]))
        targets = sorted(range(len(LAYOUTS[option])), key=lambda i: row(place(option)[i]))
        game.formation = option
        game.spots = place(option)
        game.spot_cup = [None] * len(game.spots)
        for cup, index in zip(cups, targets):
            game.spot_cup[index] = cup
            game.active[cup] = game.spots[index]
        game.rearrangements_left -= 1
        print(f"rearranged into {option}")

    async def handle(self, reader, writer):
        try:
            if not await handshake(reader, writer):
                return
            self.clients.add(writer)
            print(f"app connected ({len(self.clients)} connected)")
            await send_text(writer, json.dumps(self.game.snapshot()))

            async def reply(text):
                await send_text(writer, text)

            while True:
                opcode, payload = await read_frame(reader)
                if opcode == 0x8:
                    await send_frame(writer, 0x8, payload[:2])
                    break
                if opcode == 0x9:
                    await send_frame(writer, 0xA, payload)
                elif opcode == 0x1:
                    try:
                        message = json.loads(payload)
                    except ValueError:
                        await reply(error("Messages must be JSON"))
                        continue
                    print("app:", message)
                    await self.command(message, reply)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            if writer in self.clients:
                self.clients.discard(writer)
                print(f"app disconnected ({len(self.clients)} connected)")
            writer.close()

    async def console(self):
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return
            words = line.split()
            if not words:
                continue
            reply = lambda text: asyncio.sleep(0, print(json.loads(text).get("message", text)))
            if words[0] == "hit" and len(words) == 2 and words[1].isdigit():
                await self.command({"type": "cup_hit", "cup_id": int(words[1])}, reply)
            elif words[0] in ("rearrange", "reset"):
                await self.command({"type": words[0]}, reply)
            elif words[0] == "state":
                print(json.dumps(self.game.snapshot(), indent=2))
            else:
                print("commands: hit <cup>, rearrange, reset, state")


def error(message):
    return json.dumps({"type": "error", "message": message})


# ---- Minimal WebSocket (RFC 6455) server side ----

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


async def handshake(reader, writer):
    request = await reader.readuntil(b"\r\n\r\n")
    headers = {}
    for line in request.decode("latin-1").split("\r\n")[1:]:
        if ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip().lower()] = value.strip()
    key = headers.get("sec-websocket-key")
    if not key or "websocket" not in headers.get("upgrade", "").lower():
        writer.write(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        return False
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(
        "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode()
    )
    await writer.drain()
    return True


async def read_frame(reader):
    first, second = await reader.readexactly(2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        (length,) = struct.unpack("!H", await reader.readexactly(2))
    elif length == 127:
        (length,) = struct.unpack("!Q", await reader.readexactly(8))
    mask = await reader.readexactly(4) if second & 0x80 else b"\0\0\0\0"
    data = await reader.readexactly(length)
    return opcode, bytes(b ^ mask[i % 4] for i, b in enumerate(data))


async def send_frame(writer, opcode, payload):
    header = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header += bytes([n])
    elif n < 65536:
        header += bytes([126]) + struct.pack("!H", n)
    else:
        header += bytes([127]) + struct.pack("!Q", n)
    writer.write(header + payload)
    await writer.drain()


async def send_text(writer, text):
    await send_frame(writer, 0x1, text.encode())


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="0.0.0.0", help="interface to listen on (default: all)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--start", default="triangle_10", choices=["triangle_10", "triangle_6"])
    parser.add_argument("--move-seconds", type=float, default=1.0, help="fake gantry time per move")
    args = parser.parse_args()

    game = Game(args.start)
    game.move_seconds = args.move_seconds
    server = Server(game)

    listener = await asyncio.start_server(server.handle, args.host, args.port)
    print(f"Mock table on ws://{args.host}:{args.port}/  ({args.start})")
    print("Type: hit <cup>, rearrange, reset, state")
    async with listener:
        await asyncio.gather(listener.serve_forever(), server.console())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
