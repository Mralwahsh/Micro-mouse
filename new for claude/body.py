# body.py
"""The physical robot in the simulated world - NOT part of the firmware.

The firmware (micromouse.py) commands a forward speed and a turn rate and only
learns what happened from its wheel encoders. This class is what really
happens: the motors take MOTOR_TAU_S to follow a command, the wheels are
slightly different sizes and they slip, and the TOF sensors report where the
body was a moment ago (each sensor's latency) - so the true pose weaves and wanders away from
where the mouse believes it is.
"""
import math
import random
from collections import deque
import numpy as np
from sensors import body_to_world
from config import (WHEEL_TRACK_CM, WHEEL_SLIP_NOISE, MOUSE_WIDTH_CM, MOUSE_LENGTH_CM,
                    MOTOR_TAU_S, SENSORS, PHYSICS_HZ)

HW, HL = MOUSE_WIDTH_CM / 2, MOUSE_LENGTH_CM / 2
OUTLINE = [(-HW, HL), (0, HL), (HW, HL), (HW, 0), (HW, -HL), (0, -HL), (-HW, -HL), (-HW, 0)]


class RobotBody:
    def __init__(self, px, py, theta, wheel_gain, rng=random):
        self.px, self.py, self.theta = px, py, theta      # TRUE pose (cm, cm, rad)
        self.gain_l, self.gain_r = wheel_gain             # real / assumed wheel diameter
        self.wl = self.wr = 0.0                           # wheel speeds as the encoders count them, cm/s
        self.rng = rng
        self.history = deque(maxlen=round(max(s["latency"] for s in SENSORS) * PHYSICS_HZ) + 1)
        self.history.append((px, py, theta))

    def step(self, v, omega, dt):
        """Command a forward speed (cm/s) and turn rate (rad/s, + = clockwise) for dt.

        Returns what the encoders measured this tick: (distance cm, turn rad).
        """
        half = omega * WHEEL_TRACK_CM / 2
        k = min(1.0, dt / MOTOR_TAU_S)                    # motors lag behind the command
        self.wl += (v + half - self.wl) * k
        self.wr += (v - half - self.wr) * k
        # the ground moves differently from what the encoders count: wheel-size mismatch + slip
        gl = self.wl * self.gain_l * (1 + self.rng.gauss(0, WHEEL_SLIP_NOISE))
        gr = self.wr * self.gain_r * (1 + self.rng.gauss(0, WHEEL_SLIP_NOISE))
        v_true, w_true = (gl + gr) / 2, (gl - gr) / WHEEL_TRACK_CM
        self.theta += w_true * dt
        self.px += math.cos(self.theta) * v_true * dt
        self.py += math.sin(self.theta) * v_true * dt
        self.history.append((self.px, self.py, self.theta))
        return (self.wl + self.wr) / 2 * dt, (self.wl - self.wr) / WHEEL_TRACK_CM * dt

    def pose_ago(self, seconds):
        """Where the body was `seconds` ago - what a sensor with that latency is describing."""
        return self.history[max(0, len(self.history) - 1 - round(seconds * PHYSICS_HZ))]

    def crashed(self, sensor_array):
        """True if any point of the body outline is inside a wall or post."""
        pts = np.array([body_to_world(self.px, self.py, self.theta, bx, by) for bx, by in OUTLINE])
        b = sensor_array.boxes
        inside = ((b[None, :, 0] <= pts[:, None, 0]) & (pts[:, None, 0] <= b[None, :, 2]) &
                  (b[None, :, 1] <= pts[:, None, 1]) & (pts[:, None, 1] <= b[None, :, 3]))
        return bool(inside.any())
