"""
Gantry interface for the table server.

GameEngine.execute calls gantry.move(step) once per cup movement and
waits for it to return. move() runs in a worker thread, so it may
block (for example, waiting for the UNO Q microcontroller to reply
that the move finished).

A real gantry implements the same move(step) method: send
step.path (waypoints in mm, gantry workspace coordinates) to the
microcontroller, wait for its "done", and raise GantryError if it
reports a fault or doesn't answer in time.
"""

import logging
import time

from movement_planner import path_cost


log = logging.getLogger(__name__)


class GantryError(Exception):
    """The gantry could not complete a move."""


class SimulatedGantry:
    """
    Stands in for the real gantry: logs each move and waits as long
    as the move would take at the given speed.
    """

    def __init__(self, speed_mm_s=250.0, settle_s=0.3):
        self.speed_mm_s = speed_mm_s
        self.settle_s = settle_s

    def move(self, step):
        distance = path_cost(step.path)
        seconds = self.settle_s
        if self.speed_mm_s > 0:
            seconds += distance / self.speed_mm_s

        log.info(
            "Gantry (simulated): %s, cup %s, %d waypoints, %.0f mm, %.1f s",
            step.name, step.cup_id, len(step.path), distance, seconds
        )

        if seconds > 0:
            time.sleep(seconds)
