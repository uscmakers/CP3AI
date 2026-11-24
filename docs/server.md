# Table server

`software/server.py` runs the game on the UNO Q's Linux side (the
microprocessor). It connects the computer vision, the game logic
(`GameEngine`), the gantry and the iOS app:

```
CV ──cup_hit (x, y)──►  server  ──each move──►  gantry (UNO Q microcontroller)
iOS app ◄──state───────  │  ▲
iOS app ──commands─────►─┘  └── GameEngine: rules, cup positions, move planning
```

Python 3.10 or later, standard library only: nothing to install.

## Running it

```sh
cd software
python3 server.py                     # port 8765, triangle_6, simulated gantry
python3 server.py --start triangle_10 --speed 0    # instant moves
python3 server.py --help
```

Type into its terminal to stand in for the camera or the app:

| Command | Does |
|---|---|
| `hit 3` | cup 3 was hit |
| `hitxy 405 86` | a hit at table position x=405 mm, y=86 mm, as the CV would report it |
| `rearrange` | rearrange into the offered formation |
| `reset` / `reset triangle_10` | re-rack |
| `state` | print the current state |

Connect the iOS app to the machine's address (in the simulator, `127.0.0.1`).

Tests: `cd software && python3 -m unittest discover -s tests -v`

## Messages

All messages, for the app and the CV, are in
[`websocket-protocol.md`](websocket-protocol.md). In short: the server sends
the full `state` on connect and after every change; clients send `cup_hit`
(by `cup_id`, or by `x_mm`/`y_mm` from the CV), `rearrange`, `reset` and
`get_state`. While cups are moving, commands are rejected, never queued.

## For the CV team (UNO Q microprocessor)

1. Open a WebSocket to `ws://127.0.0.1:8765/` (the server runs on the same
   Linux side). The first message you receive is the full `state`, and a new
   one arrives after every change.
2. When a ball lands in a cup, send one `cup_hit` with the cup's center in
   **table millimeters**: the gantry workspace, with x across the table
   (0 to 810) and y from the back edge toward the front (0 to 1219). The
   origin is the back corner that `motion_viewer.py` draws at the bottom
   left; confirm which physical corner that is on the real table.
   Converting camera pixels to these coordinates (a homography from a
   one-time calibration) is on the CV side.
3. Report a hit only after several consecutive frames agree, once per hit.
4. Don't report anything while the latest state says `busy: true`. Cups
   moving under the gantry are not hits. The server drops them anyway.
5. Optional: compare the detected cups with the `cups` list in the state
   (positions in mm) to check calibration.

Any language with a WebSocket client works. In Python, a small client
like the one in `software/tests/test_server.py` is enough.

## For the electrical team (UNO Q microcontroller)

The server calls `gantry.move(step)` once per cup movement and waits for it
to return. Today `SimulatedGantry` in `software/gantry.py` just waits. A real
gantry class needs only that one method:

- `step.path`: waypoints `(x, y)` in mm, gantry workspace coordinates. The
  first is where the cup is, the last is where it goes. Straight lines between
  waypoints are collision-free; don't cut corners.
- Expected sequence per step: travel with the magnet disengaged to
  `path[0]`, engage it (servo lift), follow the waypoints, disengage it,
  report done.
- Return when the cup has arrived. Raise `GantryError` on a fault or a
  timeout. The server then tells every app the gantry stopped, and the engine
  records the cup back at its start.

Still to agree on:

- **The link** between the Linux side and the microcontroller (Arduino's
  Bridge RPC or serial) and the message format, for example
  `MOVE x1,y1;x2,y2;...` followed by `DONE` or `ERR <reason>`.
- **Homing** at startup and how the server is told it finished.
- **Speeds** and what counts as a timeout.

## Known limitation: planning time

Planning a move takes a few seconds on a laptop (about 4 s for a direct park
and 8 s for a boxed-in middle cup), because the A* in `movement_planner.py`
is pure Python. The UNO Q's processor is several times slower. The app shows
"Moving cups…" during planning, but long waits will be noticeable. Measure it
on the board early. If it's too slow, the A* grid resolution and the number of
candidate paths tried are the first things to tune.
