# body.py
"""The physical robot in the simulated world - NOT part of the firmware.

The firmware (micromouse.py) commands a forward speed and a turn rate. There are no
wheel encoders: all it gets back is the IMU's gyro reading. This class is what really
happens: the motors run open loop and take MOTOR_TAU_S to follow a command, each one
runs a few percent faster or slower than commanded, the wheels slip, the gyro has an
offset, noise and a scale error, and the TOF sensors report where the body was a moment
ago (each sensor's latency) - so the true pose wanders away from where the mouse believes it is.
"""
import math
import random
from collections import deque
import numpy as np
from sensors import body_to_world
from config import (WHEEL_TRACK_CM, WHEEL_SLIP_NOISE, MOUSE_WIDTH_CM, MOUSE_LENGTH_CM,
                    MOTOR_TAU_S, SENSORS, PHYSICS_HZ, GYRO_NOISE_DEG_S, GYRO_BIAS_DEG_S,
                    GYRO_BIAS_WALK_DEG_S, GYRO_SCALE_ERROR, GYRO_RANGE_DEG_S)

HW, HL = MOUSE_WIDTH_CM / 2, MOUSE_LENGTH_CM / 2
OUTLINE = [(-HW, HL), (0, HL), (HW, HL), (HW, 0), (HW, -HL), (0, -HL), (-HW, -HL), (-HW, 0)]


class Gyro:
    """The IMU's (BMX055) z-axis gyro. One per robot: it keeps its offset (which slowly wanders)
    and its sensitivity error from run to run."""
    def __init__(self, rng=random):
        self.rng = rng
        self.bias = math.radians(rng.gauss(0, GYRO_BIAS_DEG_S))      # rad/s read when standing still
        self.scale = 1 + rng.gauss(0, GYRO_SCALE_ERROR)

    def read(self, true_rate, dt):
        """What the gyro reports (rad/s) while the body really turns at true_rate."""
        self.bias += math.radians(self.rng.gauss(0, GYRO_BIAS_WALK_DEG_S * math.sqrt(dt)))
        rate = true_rate * self.scale + self.bias + math.radians(self.rng.gauss(0, GYRO_NOISE_DEG_S))
        limit = math.radians(GYRO_RANGE_DEG_S)
        return max(-limit, min(limit, rate))                 # past its range it just reads the limit


class RobotBody:
    def __init__(self, px, py, theta, motor_gain, gyro, rng=random):
        self.px, self.py, self.theta = px, py, theta      # TRUE pose (cm, cm, rad)
        self.gain_l, self.gain_r = motor_gain             # real / commanded speed of each motor
        self.gyro = gyro
        self.wl = self.wr = 0.0                           # commanded wheel speeds after the motor lag, cm/s
        self.rng = rng
        self.history = deque(maxlen=round(max(s["latency"] for s in SENSORS) * PHYSICS_HZ) + 1)
        self.history.append((px, py, theta))

    def step(self, v, omega, dt):
        """Command a forward speed (cm/s) and turn rate (rad/s, + = clockwise) for dt.

        Returns the gyro's reading (rad/s) - the only thing the firmware learns back.
        """
        half = omega * WHEEL_TRACK_CM / 2
        k = min(1.0, dt / MOTOR_TAU_S)                    # motors lag behind the command
        self.wl += (v + half - self.wl) * k
        self.wr += (v - half - self.wr) * k
        # open-loop motors: each runs a little faster / slower than commanded, and the wheels slip
        gl = self.wl * self.gain_l * (1 + self.rng.gauss(0, WHEEL_SLIP_NOISE))
        gr = self.wr * self.gain_r * (1 + self.rng.gauss(0, WHEEL_SLIP_NOISE))
        v_true, w_true = (gl + gr) / 2, (gl - gr) / WHEEL_TRACK_CM
        self.theta += w_true * dt
        self.px += math.cos(self.theta) * v_true * dt
        self.py += math.sin(self.theta) * v_true * dt
        self.history.append((self.px, self.py, self.theta))
        return self.gyro.read(w_true, dt)

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
