# Table WebSocket protocol (v1)

The game server (Python, on the UNO Q's Linux side) owns the game. It wraps
`GameEngine` from `software/game_engine.py`. Apps connect over a WebSocket on
the local network, display the state the server sends, and send commands.
Apps never compute moves themselves.

- URL: `ws://<host>:8765/` (for example `ws://unoq.local:8765/`)
- Every message is one JSON object in a text frame, with a `type` field.
- Coordinates are millimeters on the gantry workspace, matching `game_engine.py`.
  Positive y points toward the front of the table (the top of the app's screen).
- Ignore unknown `type`s and unknown fields, so either side can add things later.

## Server → app

### `state`

Sent to a client right after it connects, and to every client after any
change: a cup parked, a rearrangement finished, a reset, or `busy` changing.
It is the full state each time, so a client that misses one message recovers
on the next.

```json
{
  "type": "state",
  "version": 12,
  "formation": "triangle_6",
  "start_formation": "triangle_6",
  "game_started": true,
  "busy": false,
  "remaining": 5,
  "rearrangements_left": 1,
  "rearrange_option": "backpack_kid_5",
  "cup_diameter_mm": 92,
  "gantry": {"x_mm": 61.0, "y_mm": 61.0},
  "cups": [
    {"id": 1, "status": "active", "formation_index": 1, "x_mm": 405.0, "y_mm": 86.0},
    {"id": 0, "status": "parked", "slot_id": "L1", "x_mm": 61.0, "y_mm": 61.0}
  ],
  "spots": [
    {"index": 0, "x_mm": 313.0, "y_mm": 86.0, "cup_id": 0},
    {"index": 1, "x_mm": 405.0, "y_mm": 86.0, "cup_id": 1}
  ]
}
```

Everything except `type` and `spots` is what `GameEngine.snapshot()` returns.

`spots` lists every position of the current formation, including those whose
cup has been hit. `cup_id` is the cup in that spot, or the cup that was last
there; it is `null` if no cup was ever assigned to it. The app draws a spot as
a cup if that cup is `active`, otherwise as an empty outline. Build it from
`engine.formation_positions` and `engine.formation_index`. A server that
leaves `spots` out still works: the app then draws only the active cups.

`busy` is true while the gantry is moving. The app disables its buttons, and
the server rejects commands, until a `state` with `busy: false` arrives.

### `error`

A command was rejected or planning failed. The game state is unchanged.

```json
{"type": "error", "message": "No rearrangement offered for 4 cups"}
```

Send the text of `GameError` / `PlanningError` as `message`; the app shows it.

## App and CV → server

| Message | Engine call |
|---|---|
| `{"type": "cup_hit", "cup_id": 3}` | `execute(plan_cup_removal(3))` |
| `{"type": "cup_hit", "x_mm": 405.0, "y_mm": 86.0, "confidence": 0.93}` | find the cup in play within one cup radius of (x, y), then as above |
| `{"type": "rearrange", "formation": "backpack_kid_5"}` | `execute(plan_rearrangement("backpack_kid_5"))` |
| `{"type": "reset"}` | `reset()` (players have re-racked the cups) |
| `{"type": "reset", "start_formation": "triangle_10"}` | `reset("triangle_10")`; `triangle_10` or `triangle_6` |
| `{"type": "get_state"}` | reply with `state` |

The app sends `cup_hit` with a `cup_id`, as a manual correction for a hit the
camera missed. The CV connects to the same socket and sends `cup_hit` with
table coordinates. `confidence` is optional; the server ignores hits below its
`--min-confidence`.

Each command gets either a new `state` broadcast (it changed something) or an
`error` sent back to the client that sent it.

One action runs at a time. While cups are moving (`busy: true`), every
command, CV hits included, is answered with an error and dropped, never queued.
