# sensors.py
import math
import random
from dataclasses import dataclass
import numpy as np
from config import (COLS, ROWS, CELL_SIZE_CM, WALL_THICKNESS_CM, SENSORS,
                    TOF_NOISE_CM, TOF_NOISE_FRAC, IR_NOISE_CM, SENSOR_DROPOUT)

HALF_WALL = WALL_THICKNESS_CM / 2


@dataclass
class Reading:
    """What one sensor reports for one sample. All coordinates in real-world cm.

    Only `distance` is information a real sensor gives; origin / direction come
    from where the mouse believes the sensor is mounted and pointing.
    """
    sensor: dict
    origin: tuple                  # where the beam leaves the mouse
    direction: tuple               # unit vector of the beam
    distance: float | None         # measured (noisy) distance, None = nothing within range
    end: tuple                     # measured hit point, or the max-range point


def body_to_world(px, py, theta, bx, by):
    """Mouse body frame (x = right, y = forward) to world cm. theta: heading angle, y axis points down."""
    fx, fy = math.cos(theta), math.sin(theta)
    rx, ry = -fy, fx
    return px + rx * bx + fx * by, py + ry * bx + fy * by


class SensorArray:
    """Simulated distance sensors firing against the real wall/post geometry of a maze.

    World frame: cm, origin at the centre of the top-left post, x to the right,
    y downwards. Cell (x, y) spans [18x, 18x+18] between post centres; walls and
    posts are WALL_THICKNESS_CM thick and centred on the grid lines.
    """
    def __init__(self, maze):
        self.maze = maze
        boxes = []
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if i == COLS // 2 and j == ROWS // 2:      # no post in the middle of the goal room
                    continue
                gx, gy = i * CELL_SIZE_CM, j * CELL_SIZE_CM
                boxes.append((gx - HALF_WALL, gy - HALF_WALL, gx + HALF_WALL, gy + HALF_WALL))
        for x in range(COLS):
            for y in range(ROWS):
                walls, gx, gy = maze.grid[x][y].walls, x * CELL_SIZE_CM, y * CELL_SIZE_CM
                if walls['N']:
                    boxes.append((gx + HALF_WALL, gy - HALF_WALL, gx + CELL_SIZE_CM - HALF_WALL, gy + HALF_WALL))
                if walls['W']:
                    boxes.append((gx - HALF_WALL, gy + HALF_WALL, gx + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL))
                if y == ROWS - 1 and walls['S']:
                    boxes.append((gx + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL,
                                  gx + CELL_SIZE_CM - HALF_WALL, gy + CELL_SIZE_CM + HALF_WALL))
                if x == COLS - 1 and walls['E']:
                    boxes.append((gx + CELL_SIZE_CM - HALF_WALL, gy + HALF_WALL,
                                  gx + CELL_SIZE_CM + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL))
        self.boxes = np.array(boxes, dtype=float)       # (N, 4): xmin, ymin, xmax, ymax

    def true_distance(self, ox, oy, dx, dy, max_range):
        """Exact distance to the first solid surface along the beam (None = nothing in range)."""
        b = self.boxes
        near, far = [], []
        for o, d, lo, hi in ((ox, dx, b[:, 0], b[:, 2]), (oy, dy, b[:, 1], b[:, 3])):
            if d == 0:     # beam parallel to this axis: either always inside the slab or never
                inside = (lo <= o) & (o <= hi)
                near.append(np.where(inside, -np.inf, np.inf))
                far.append(np.where(inside, np.inf, -np.inf))
            else:
                t1, t2 = (lo - o) / d, (hi - o) / d
                near.append(np.minimum(t1, t2))
                far.append(np.maximum(t1, t2))
        t_near = np.maximum(near[0], near[1])
        t_far = np.minimum(far[0], far[1])
        hits = (t_near <= t_far) & (t_far >= 0) & (t_near <= max_range)
        if not hits.any():
            return None
        return float(max(0.0, t_near[hits].min()))

    def scan(self, px, py, theta, rng=random):
        """Read every sensor from the pose (px, py, theta). Distances carry sensor noise."""
        readings = []
        for s in SENSORS:
            ox, oy = body_to_world(px, py, theta, s["x"], s["y"])
            a = theta + math.radians(s["angle"])
            dx, dy = math.cos(a), math.sin(a)
            if abs(dx) < 1e-12: dx = 0.0
            if abs(dy) < 1e-12: dy = 0.0

            dist = self.true_distance(ox, oy, dx, dy, s["range"])
            if dist is not None:
                sigma = IR_NOISE_CM if s["kind"] == "IR" else TOF_NOISE_CM + TOF_NOISE_FRAC * dist
                dist = max(0.0, dist + rng.gauss(0.0, sigma))
                if dist > s["range"] or rng.random() < SENSOR_DROPOUT:
                    dist = None
            reach = dist if dist is not None else s["range"]
            readings.append(Reading(s, (ox, oy), (dx, dy), dist, (ox + dx * reach, oy + dy * reach)))
        return readings
