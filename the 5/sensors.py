# sensors.py
import math
import random
from dataclasses import dataclass
import numpy as np
from config import (COLS, ROWS, CELL_SIZE_CM, WALL_THICKNESS_CM, SENSORS,
                    MIN_NOISE_CM, SENSOR_DROPOUT)

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


def noise_sigma(s, distance):
    """1-sigma error of a reading. Accuracy is quoted as the +/- band that 95 % (2 sigma) of
    readings fall in, as a fraction of the distance: 85 % accurate -> +/-15 % -> sigma 7.5 %."""
    return max(MIN_NOISE_CM, (1 - s["accuracy"]) / 2 * distance)


def body_to_world(px, py, theta, bx, by):
    """Mouse body frame (x = right, y = forward) to world cm. theta: heading angle, y axis points down."""
    fx, fy = math.cos(theta), math.sin(theta)
    rx, ry = -fy, fx
    return px + rx * bx + fx * by, py + ry * bx + fy * by


def beam(px, py, theta, s):
    """Origin and unit direction of sensor s when the mouse is at pose (px, py, theta)."""
    ox, oy = body_to_world(px, py, theta, s["x"], s["y"])
    a = theta + math.radians(s["angle"])
    dx, dy = math.cos(a), math.sin(a)
    return ox, oy, (0.0 if abs(dx) < 1e-12 else dx), (0.0 if abs(dy) < 1e-12 else dy)


def reading_at(px, py, theta, r):
    """The same measured distance, placed at another pose (e.g. where the mouse BELIEVES it is)."""
    ox, oy, dx, dy = beam(px, py, theta, r.sensor)
    reach = r.distance if r.distance is not None else r.sensor["range"]
    return Reading(r.sensor, (ox, oy), (dx, dy), r.distance, (ox + dx * reach, oy + dy * reach))


class SensorArray:
    """Simulated distance sensors firing against the real wall/post geometry of a maze.

    World frame: cm, origin at the centre of the top-left post, x to the right,
    y downwards. Cell (x, y) spans [18x, 18x+18] between post centres; walls and
    posts are WALL_THICKNESS_CM thick and centred on the grid lines.
    """
    def __init__(self, maze, known_only=False):
        """known_only: build from a MEMORY maze, using only walls confirmed to be there
        (the firmware's own view of the world, for predicting what a sensor should read)."""
        self.maze = maze
        boxes, kinds = [], []
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if i == COLS // 2 and j == ROWS // 2:      # no post in the middle of the goal room
                    continue
                gx, gy = i * CELL_SIZE_CM, j * CELL_SIZE_CM
                boxes.append((gx - HALF_WALL, gy - HALF_WALL, gx + HALF_WALL, gy + HALF_WALL))
                kinds.append('post')
        for x in range(COLS):
            for y in range(ROWS):
                cell, gx, gy = maze.grid[x][y], x * CELL_SIZE_CM, y * CELL_SIZE_CM

                def closed(d):
                    return cell.walls[d] and (cell.walls_known[d] or not known_only)
                if closed('N'):
                    boxes.append((gx + HALF_WALL, gy - HALF_WALL, gx + CELL_SIZE_CM - HALF_WALL, gy + HALF_WALL))
                    kinds.append('H')
                if closed('W'):
                    boxes.append((gx - HALF_WALL, gy + HALF_WALL, gx + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL))
                    kinds.append('V')
                if y == ROWS - 1 and closed('S'):
                    boxes.append((gx + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL,
                                  gx + CELL_SIZE_CM - HALF_WALL, gy + CELL_SIZE_CM + HALF_WALL))
                    kinds.append('H')
                if x == COLS - 1 and closed('E'):
                    boxes.append((gx + CELL_SIZE_CM - HALF_WALL, gy + HALF_WALL,
                                  gx + CELL_SIZE_CM + HALF_WALL, gy + CELL_SIZE_CM - HALF_WALL))
                    kinds.append('V')
        self.boxes = np.array(boxes, dtype=float)       # (N, 4): xmin, ymin, xmax, ymax
        self.kinds = kinds                              # 'post', 'H' (horizontal wall) or 'V' (vertical wall)

    def true_distance(self, ox, oy, dx, dy, max_range):
        """Exact distance to the first solid surface along the beam (None = nothing in range)."""
        hit = self.first_hit(ox, oy, dx, dy, max_range)
        return None if hit is None else hit[0]

    def first_hit(self, ox, oy, dx, dy, max_range):
        """(distance, kind, axis) of the first surface along the beam, or None if nothing is in range.
        axis is 'x' when the beam hit a face whose normal is along x (a vertical face), else 'y'."""
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
        t = np.where(hits, t_near, np.inf)
        i = int(np.argmin(t))
        return float(max(0.0, t[i])), self.kinds[i], ('x' if near[0][i] >= near[1][i] else 'y')

    def scan(self, px, py, theta, which=SENSORS, rng=random):
        """Read the sensors in `which` from the pose (px, py, theta). Distances carry sensor noise."""
        readings = []
        for s in which:
            ox, oy, dx, dy = beam(px, py, theta, s)

            dist = self.true_distance(ox, oy, dx, dy, s["range"])
            if dist is not None:
                dist = max(0.0, dist + rng.gauss(0.0, noise_sigma(s, dist)))
                if dist > s["range"] or rng.random() < SENSOR_DROPOUT:
                    dist = None
            reach = dist if dist is not None else s["range"]
            readings.append(Reading(s, (ox, oy), (dx, dy), dist, (ox + dx * reach, oy + dy * reach)))
        return readings
