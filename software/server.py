"""
Cup pong table server.

Runs the game on the UNO Q's Linux side. It connects:

- the computer vision, which reports hits,
- the game logic (GameEngine), which plans the cup movements,
- the gantry, which carries them out (simulated for now), and
- the iOS app, which shows the live state and sends commands.

Everyone talks to it over one WebSocket (default port 8765) using
JSON messages; see docs/websocket-protocol.md. The CV sends the same
cup_hit message the app does, with table coordinates instead of a
cup ID:

    {"type": "cup_hit", "x_mm": 405.0, "y_mm": 86.0, "confidence": 0.93}

Run it:

    python3 server.py                       # simulated gantry
    python3 server.py --start triangle_10 --speed 500

Type commands into its terminal to test without the CV or the app:

    hit 3            cup 3 was hit
    hitxy 405 86     a hit at table position x=405 mm, y=86 mm
    rearrange        rearrange into the offered formation
    reset [name]     re-rack (optionally triangle_10 or triangle_6)
    state            print the current state
"""

import argparse
import asyncio
import json
import logging
import math
import sys

from game_engine import (
    GameEngine,
    GameError,
    START_FORMATION,
    START_FORMATIONS,
)
from gantry import SimulatedGantry
from movement_planner import TablePosition
import ws


log = logging.getLogger("server")

DEFAULT_PORT = 8765


class TableServer:
    """
    Owns the GameEngine and serializes everything that changes it:
    one action (plan + gantry moves) at a time. Commands that arrive
    while an action runs are rejected with "busy", never queued, so
    camera hits seen while cups are sliding are dropped.
    """

    def __init__(self, engine, gantry, min_confidence=0.0):
        self.engine = engine
        self.gantry = gantry
        self.min_confidence = min_confidence

        self.clients = set()
        self._action = asyncio.Lock()
        self._tasks = set()

        # Last state sent to clients. Only refreshed between actions,
        # never while a worker thread is changing the engine.
        self._state = self._snapshot()

    # --------------------------------------------------------
    # Connections
    # --------------------------------------------------------

    async def handle_connection(self, reader, writer):
        connection = await ws.accept(reader, writer)
        if connection is None:
            return

        self.clients.add(connection)
        log.info("Client %s connected (%d connected)", connection.peer, len(self.clients))

        try:
            await connection.send(json.dumps(self._state))

            while True:
                try:
                    text = await connection.recv()
                except ws.WebSocketError as error:
                    log.warning("Client %s: %s", connection.peer, error)
                    break

                if text is None:
                    break

                # Handle each message in its own task so this loop keeps
                # answering pings and get_state while the gantry moves.
                task = asyncio.create_task(self.handle_text(connection, text))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

        except (ConnectionError, OSError, asyncio.TimeoutError):
            pass

        finally:
            self.clients.discard(connection)
            await connection.close()
            log.info("Client %s disconnected (%d connected)", connection.peer, len(self.clients))

    async def handle_text(self, connection, text):
        async def reply(message):
            try:
                await connection.send(json.dumps(message))
            except (ConnectionError, OSError, asyncio.TimeoutError):
                pass

        try:
            message = json.loads(text)
        except ValueError:
            await reply(error_message("Messages must be JSON"))
            return

        if not isinstance(message, dict):
            await reply(error_message("Messages must be JSON objects"))
            return

        log.info("From %s: %s", connection.peer, text)
        await self.handle_message(message, reply)

    # --------------------------------------------------------
    # Commands
    # --------------------------------------------------------

    async def handle_message(self, message, reply):
        """Dispatch one command. reply(message) answers its sender only."""

        kind = message.get("type")

        if kind == "get_state":
            await reply(self._state)

        elif kind == "cup_hit":
            await self.cup_hit(message, reply)

        elif kind == "rearrange":
            formation = message.get("formation")
            await self._run_action(
                reply,
                lambda: self.engine.check_rearrangement(formation),
                lambda: self.engine.plan_rearrangement(formation),
            )

        elif kind == "reset":
            await self.reset(message.get("start_formation"), reply)

        else:
            await reply(error_message(f"Unknown message type: {kind!r}"))

    async def cup_hit(self, message, reply):
        cup_id = message.get("cup_id")
        confidence = message.get("confidence")

        if confidence is not None:
            if not is_number(confidence):
                await reply(error_message("confidence must be a number"))
                return
            if confidence < self.min_confidence:
                log.info("Ignoring hit with confidence %.2f", confidence)
                await reply(error_message(
                    f"Hit ignored: confidence {confidence:.2f} is below "
                    f"{self.min_confidence:.2f}"
                ))
                return

        if cup_id is None:
            x, y = message.get("x_mm"), message.get("y_mm")
            if not (is_number(x) and is_number(y)):
                await reply(error_message(
                    "cup_hit needs cup_id, or x_mm and y_mm"
                ))
                return

            if self._action.locked():
                await reply(busy_message())
                return

            cup_id = self.engine.find_cup_near(TablePosition(x, y))
            if cup_id is None:
                await reply(error_message(
                    f"No cup in play at x={x:.0f} mm, y={y:.0f} mm"
                ))
                return

            log.info("Hit at (%.0f, %.0f) mm is cup %s", x, y, cup_id)

        elif not isinstance(cup_id, int) or isinstance(cup_id, bool):
            await reply(error_message("cup_id must be an integer"))
            return

        await self._run_action(
            reply,
            lambda: self.engine.check_cup_removal(cup_id),
            lambda: self.engine.plan_cup_removal(cup_id),
        )

    async def reset(self, start_formation, reply):
        if start_formation is not None and start_formation not in START_FORMATIONS:
            await reply(error_message(
                f"start_formation must be one of {', '.join(START_FORMATIONS)}"
            ))
            return

        if self._action.locked():
            await reply(busy_message())
            return

        async with self._action:
            try:
                self.engine.reset(start_formation)
            except GameError as error:
                await reply(error_message(str(error)))
                return
            log.info("Reset to %s", self.engine.layout_name)
            await self._publish(self._snapshot())

    async def _run_action(self, reply, check_fn, plan_fn):
        """
        Plan and execute one action: check the rules (a quick check,
        so a bad command never shows as busy), tell clients the table
        is busy, plan in a worker thread (A* can take a while), drive
        the gantry through every step, then publish the new state.
        """

        if self._action.locked():
            await reply(busy_message())
            return

        async with self._action:
            try:
                check_fn()
            except GameError as error:
                log.info("Rejected: %s", error)
                await reply(error_message(str(error)))
                return

            await self._publish({**self._state, "busy": True})

            try:
                plan = await asyncio.to_thread(plan_fn)
                log.info(
                    "Plan: %s, %d moves, %.0f mm",
                    plan.kind, len(plan.steps), plan.cost
                )
                await asyncio.to_thread(
                    self.engine.execute, plan, self.gantry.move
                )

            except GameError as error:
                # Rejected or no plan found: nothing moved.
                log.info("Rejected: %s", error)
                await reply(error_message(str(error)))

            except Exception as error:
                # The gantry failed partway. The engine has recorded
                # where each cup ended up; everyone needs to know.
                log.exception("Action failed")
                await self._broadcast(error_message(
                    f"The gantry stopped: {error}. Check the table before continuing."
                ))

            finally:
                await self._publish(self._snapshot())

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    def _snapshot(self):
        return {"type": "state", **self.engine.snapshot()}

    async def _publish(self, state):
        self._state = state
        await self._broadcast(state)

    async def _broadcast(self, message):
        if not self.clients:
            return

        text = json.dumps(message)
        clients = list(self.clients)
        results = await asyncio.gather(
            *(client.send(text) for client in clients),
            return_exceptions=True,
        )

        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                log.info("Dropping client %s: %s", client.peer, result)
                self.clients.discard(client)
                await client.close()

    # --------------------------------------------------------
    # Terminal commands (for testing without CV or the app)
    # --------------------------------------------------------

    async def console(self):
        loop = asyncio.get_running_loop()

        async def reply(message):
            if message.get("type") == "error":
                print("error:", message["message"], flush=True)

        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                return

            words = line.split()
            if not words:
                continue

            command, args = words[0].lower(), words[1:]

            try:
                if command == "hit" and len(args) == 1:
                    await self.handle_message(
                        {"type": "cup_hit", "cup_id": int(args[0])}, reply
                    )
                elif command == "hitxy" and len(args) == 2:
                    await self.handle_message(
                        {"type": "cup_hit", "x_mm": float(args[0]), "y_mm": float(args[1])},
                        reply,
                    )
                elif command == "rearrange" and not args:
                    await self.handle_message({"type": "rearrange"}, reply)
                elif command == "reset" and len(args) <= 1:
                    await self.handle_message(
                        {"type": "reset", "start_formation": args[0] if args else None},
                        reply,
                    )
                elif command == "state" and not args:
                    print(json.dumps(self._state, indent=2), flush=True)
                else:
                    print(
                        "commands: hit <cup>, hitxy <x_mm> <y_mm>, rearrange, "
                        "reset [triangle_10|triangle_6], state",
                        flush=True,
                    )
            except ValueError:
                print("numbers expected", flush=True)


def error_message(text):
    return {"type": "error", "message": text}


def busy_message():
    return error_message("Gantry is moving; try again when it stops")


def is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


async def serve(host, port, server, console=True):
    listener = await asyncio.start_server(server.handle_connection, host, port)
    addresses = ", ".join(
        f"ws://{sock.getsockname()[0]}:{sock.getsockname()[1]}/"
        for sock in listener.sockets
    )
    log.info("Table server on %s (%s)", addresses, server.engine.layout_name)

    async with listener:
        if console:
            log.info("Type: hit <cup>, hitxy <x> <y>, rearrange, reset, state")
            await asyncio.gather(listener.serve_forever(), server.console())
        else:
            await listener.serve_forever()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default="0.0.0.0", help="interface to listen on (default: all)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--start", default=START_FORMATION, choices=START_FORMATIONS,
                        help="starting formation")
    parser.add_argument("--speed", type=float, default=250.0,
                        help="simulated gantry speed in mm/s (0 = instant)")
    parser.add_argument("--min-confidence", type=float, default=0.0,
                        help="ignore CV hits reported below this confidence")
    parser.add_argument("--no-console", action="store_true",
                        help="don't read commands from the terminal")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    engine = GameEngine(start_formation=args.start)
    gantry = SimulatedGantry(speed_mm_s=args.speed, settle_s=0.3 if args.speed > 0 else 0)
    server = TableServer(engine, gantry, min_confidence=args.min_confidence)

    try:
        asyncio.run(serve(args.host, args.port, server, console=not args.no_console))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
