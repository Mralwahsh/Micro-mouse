# micromouse.py
import heapq
import math
import random
from collections import deque
from maze import Maze, START_OPENING
from mapper import Mapper
from sensors import SensorArray, reading_at
from body import RobotBody
from config import (PHYSICS_HZ, COLS, ROWS, DIRECTIONS, OPPOSITE, TARGET_CELLS, START_CELL, CELL_SIZE_CM,
                    WALL_THICKNESS_CM, SENSORS, MAX_SPEED_CM_S, SEARCH_SPEED_CM_S, EXPLORE_SPEED_CM_S, HOME_SPEED_CM_S, ACCEL_CM_S2, TURN_RADIUS_CM,
                    SEARCH_TURN_SPEED_CM_S, FAST_TURN_SPEED_CM_S, MOTOR_LAG_COMP_S, corner_speed,
                    BIG_CORNERS, BIG_TURN_RADIUS_CM, DIAGONALS, DIAG_TURN_RADIUS_CM, DIAG_SPEED_CM_S,
                    DIAG_KP, DIAG_KH, DIAG_POS_GAIN, DIAG_HEAD_GAIN, DIAG_USE_CURVE, DIAG_HERO_ONLY,
                    ARC_K_RADIUS, ARC_K_HEADING,
                    MAX_TURN_RAD_S, TURN_ACCEL_RAD_S2, WHEEL_MISMATCH, START_POS_ERROR_CM,
                    START_ANGLE_ERROR_DEG, START_BACKOFF_CM, MOUSE_LENGTH_CM, AUTO_RETURN,
                    CENTER_KP, CENTER_KH, MAX_STEER_RAD_S,
                    OBS_K_OFFSET, OBS_K_HEADING, OBS_K_CURVE)

# Heading angle of each compass direction (world y axis points down, so North = -90 deg)
HEADING_ANGLE = {'E': 0.0, 'S': math.pi / 2, 'W': math.pi, 'N': -math.pi / 2}
# Time costs used to pick the quickest fast-run route
CELL_TIME = CELL_SIZE_CM / MAX_SPEED_CM_S
# a corner: slow to the turn speed and back up again, and the arc itself instead of two half cells
TURN_TIME = ((MAX_SPEED_CM_S - FAST_TURN_SPEED_CM_S) ** 2 / (ACCEL_CM_S2 * MAX_SPEED_CM_S)
             + (math.pi / 2) * TURN_RADIUS_CM / FAST_TURN_SPEED_CM_S - CELL_SIZE_CM / MAX_SPEED_CM_S)
# a U-turn still has to stop and pivot on the spot
PIVOT_TIME = MAX_SPEED_CM_S / ACCEL_CM_S2 + 2 * math.sqrt(math.pi / TURN_ACCEL_RAD_S2)
DECISION_MARGIN_CM = 1.0        # decide the next move this far before the braking point
WALL_FACE = CELL_SIZE_CM / 2 - WALL_THICKNESS_CM / 2    # centre line -> wall face (9.0 cm)
LEFT_OF = {'N': 'W', 'E': 'N', 'S': 'E', 'W': 'S'}
RIGHT_OF = {k: OPPOSITE[v] for k, v in LEFT_OF.items()}
FRONT_TOF = next(s for s in SENSORS if s["kind"] == "TOF" and s["angle"] == 0)
# sensors of one kind are read together, every `period` seconds, describing the pose `latency` ago
SENSOR_GROUPS = {k: [s for s in SENSORS if s["kind"] == k] for k in dict.fromkeys(s["kind"] for s in SENSORS)}
MAX_LATENCY_TICKS = round(max(s["latency"] for s in SENSORS) * PHYSICS_HZ)
FRONT_SAMPLES = 4               # front-wall readings averaged before re-centring at a stop
MAP_TRUST_CM = 25.0             # only readings this short correct the pose: far ones amplify heading error
ALONG_GAIN = 0.2                # share of a wall-across-the-lane error applied per reading
MAX_CURVE = 0.003               # rad/cm: a ~2% wheel-size mismatch, more than any real mouse has


def cell_center(x, y):
    return (x + 0.5) * CELL_SIZE_CM, (y + 0.5) * CELL_SIZE_CM


def _approach(value, target, max_delta):
    return value + max(-max_delta, min(max_delta, target - value))


def _wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


class Micromouse:
    """The physical robot: continuous motion, real sensing, flood-fill decisions.

    Every physics tick (PHYSICS_HZ) the mouse:

      1. SENSE  - reads its 5 sensors (2 side IR every 5 ms, 3 TOF every 25 ms, see
                  config.SENSORS). Each gives only a noisy distance. The Mapper
                  turns those distances into wall / open evidence per edge;
                  an edge enters the map only after enough agreeing readings.
      2. MOVE   - drives with limited acceleration and speed. It always brakes
                  towards a target cell centre; approaching the braking point
                  it decides the next move from that cell:
                    * straight on, and the edge ahead is confirmed open
                      -> the target moves one cell further, no stop;
                    * anything else (turn, dead end, not yet sure)
                      -> stop at the centre, then turn in place.
      3. DECIDE - classic flood fill (unknown edges assumed open). Ties break on
                  fewest turns, then unexplored cells, then a stable order. The
                  mouse only ever drives through an edge it has confirmed open.

    Pose: px / py / theta is where the firmware BELIEVES it is (wheel encoders only -
    no IMU). The real body (`self.body`, simulation only) drifts away from that.
    To stay centred the firmware runs a small observer that estimates its offset
    from the centre line, its heading error and its own wheel-mismatch curve,
    from the steering it commands plus the side-wall distances (diagonal TOFs +
    short IR guard). It steers on those estimates, so it keeps going straight
    where there are no walls too. It re-centres along the cell from the front
    wall whenever it stops facing one. Touching a wall = crash.

    Rounds: the mouse always runs the full 3 rounds. Between rounds it is
    carried back to the start by hand; the map carries over. Each round is one of:
      * SEARCH - flood fill at SEARCH_SPEED_CM_S, mapping as it goes;
      * FAST   - no exploring: follow the quickest route through confirmed-open
                 edges at full motor speed (MAX_SPEED_CM_S = 381 rpm wheels).
    A round is FAST once the map proves the best route (`solved_optimally`:
    confirmed route as short as the optimistic lower bound), and the last
    round is always FAST - that is the run that counts.
    """

    def __init__(self):
        self.target_cells = set(TARGET_CELLS)
        self.start = START_CELL
        self.reset_all()

    # ------------------------------------------------------------------ setup
    def reset_all(self):
        self.memory = Maze(is_blank_memory=True)
        self.mapper = Mapper(self.memory)
        self.sensors = None                     # built lazily against the physical maze
        self.known_view = None                  # firmware: ray-cast model of the CONFIRMED walls
        self.runs = []                          # one entry per run attempted (see begin_run)
        self.mode = "SEARCH"
        self.route = {}                         # FAST mode: cell -> direction to drive
        self.plan = {}                          # FAST mode: cell -> ("big",) or ("diag", staircase)
        self.hero_done = False                  # has a diagonal run already reached the goal?
        self.state = "IDLE"
        self.solved_optimally = False
        self.global_visited = set([self.start])
        # this robot's wheels: a fixed small size mismatch the firmware doesn't know about
        self.wheel_gain = (1 + random.gauss(0, WHEEL_MISMATCH), 1 + random.gauss(0, WHEEL_MISMATCH))
        self.est_curve = 0.0                    # firmware: learned curve from that mismatch (rad per cm)
        self._place_at_start()
        self.flood = self._flood(optimistic=True)

    def _place_at_start(self, by_hand=True):
        """Ready for a run at the BACK of the start cell, facing north: the timer only starts when
        the front edge leaves the cell, so this run-up is free speed (rule 6.1.f).

        by_hand: the operator sets it down there (a fresh placement error). Otherwise the mouse
        drove home and parked itself, so its real pose is kept exactly as it left it.
        """
        self.x, self.y = self.start
        cx, cy = cell_center(*self.start)
        if by_hand:
            self.px = cx - DIRECTIONS['N'][0] * START_BACKOFF_CM
            self.py = cy - DIRECTIONS['N'][1] * START_BACKOFF_CM
            self.theta = HEADING_ANGLE['N']
        self.heading = 'N'
        self.v = 0.0                            # forward speed, cm/s
        self.omega = 0.0                        # turn rate, rad/s
        self.motion = "AT_CENTER"               # AT_CENTER | TURN | DRIVE
        self.target = self.start                # cell centre the mouse is braking towards
        self.decided = True                     # has the move after `target` been decided?
        self.turn_to = None
        self.path_stack = [self.start]          # actual trajectory this round
        self.round_visited = set([self.start])
        self.sensor_timers = {k: g[0]["period"] for k, g in SENSOR_GROUPS.items()}   # read on the first tick
        self.latest = {}                        # sensor name -> (reading, same reading at the believed pose)
        self.readings = []                      # what the sensors last reported (from the TRUE pose)
        self.believed_readings = []             # the same distances placed at the BELIEVED pose
        self.steer = 0.0                        # centering correction, rad/s
        self.est_offset = 0.0                   # observer: cm right of the centre line
        self.est_heading = 0.0                  # observer: rad clockwise of the heading
        self.walls_seen = False                 # did a side wall correct the observer this tick?
        self.turn_settling = False
        self.pending = None                     # an arc planned ahead (starts at pending["start"])
        self.arc = None                         # the arc being driven
        self.diag = None                        # the diagonal line being driven
        self.enc_rate = 0.0                     # encoder turn this tick (rad)
        self.true_trail = []                    # telemetry: (x, y, speed) of the REAL body this run
        self.pose_hist = deque([(self.px, self.py, self.theta)], maxlen=MAX_LATENCY_TICKS + 1)
        self.front_samples = []
        self.calibrated = False                 # front-wall re-centre done at this stop?
        self.recentering = False
        self.run_clock = 0.0
        self.phase = "TO_GOAL"                  # TO_GOAL -> TO_START -> (park) -> run over
        self.nav_cells = set(self.target_cells)
        self.parked = False
        if by_hand:
            # set down by hand: never exactly on the centre or exactly straight
            err = START_POS_ERROR_CM
            self.body = RobotBody(self.px + random.uniform(-err, err), self.py + random.uniform(-err, err),
                                  self.theta + math.radians(random.uniform(-START_ANGLE_ERROR_DEG,
                                                                          START_ANGLE_ERROR_DEG)),
                                  self.wheel_gain)
        self.memory.grid[self.x][self.y].discovered = True
        self.front_point = self._front_point()  # for the official start / finish line crossings

    def next_run_mode(self, last_chance=False):
        """Explore until the map proves the best route, then race it. On the last chance it races
        whatever route it has confirmed so far."""
        return "FAST" if (self.solved_optimally or last_chance) and self._fast_route() else "SEARCH"

    def begin_run(self, last_chance=False):
        """Send the mouse off from the start cell. It is placed by hand unless it drove home itself."""
        drove_home = bool(self.runs) and self.runs[-1]["returned"]
        self.mode = self.next_run_mode(last_chance)
        self._place_at_start(by_hand=not drove_home)
        self.route = self._fast_route() if self.mode == "FAST" else {}
        if not self.route:
            self.mode = "SEARCH"                # no confirmed route yet: keep exploring
        self.plan = self._plan_fast_path() if self.route else {}
        self.runs.append({"mode": self.mode, "time": None, "cells": 0, "max_offset": 0.0,
                          "crashed": False, "started": False, "returned": False})
        self.global_visited.add(self.start)
        self.state = "EXPLORING"
        self.flood = self._flood(optimistic=True)

    @property
    def run(self):
        return self.runs[-1] if self.runs else {"mode": self.mode, "time": None, "cells": 0,
                                                "max_offset": 0.0, "crashed": False, "started": False,
                                                "returned": False}

    def official_times(self):
        return [r["time"] for r in self.runs if r["time"] is not None]

    def _front_point(self):
        """The front edge of the REAL body - what the judges' timing gates see."""
        return (self.body.px + math.cos(self.body.theta) * MOUSE_LENGTH_CM / 2,
                self.body.py + math.sin(self.body.theta) * MOUSE_LENGTH_CM / 2)

    def _crossed(self, key, was, now):
        """Did the front edge cross this wall slot (start / finish line) between two ticks?"""
        kind, a, b = key
        if kind == 'H':
            line, along0, along1 = b * CELL_SIZE_CM, a * CELL_SIZE_CM, (a + 1) * CELL_SIZE_CM
            before, after, pos = was[1], now[1], now[0]
        else:
            line, along0, along1 = a * CELL_SIZE_CM, b * CELL_SIZE_CM, (b + 1) * CELL_SIZE_CM
            before, after, pos = was[0], now[0], now[1]
        return (before - line) * (after - line) < 0 and along0 <= pos <= along1

    def _check_timing_lines(self, physical_maze):
        """Official run time: front edge over the start line, then over the goal entrance."""
        was, now = self.front_point, self._front_point()
        self.front_point = now
        run = self.run
        if not run["started"]:
            if self._crossed(Maze.edge_key(*self.start, START_OPENING), was, now):
                run["started"] = True
        elif run["time"] is None and self._crossed(physical_maze.goal_entrance, was, now):
            run["time"] = self.run_clock

    # -------------------------------------------------------------- main tick
    def update(self, physical_maze, dt):
        if self.state != "EXPLORING":
            return
        if self.run["started"] and self.run["time"] is None:
            self.run_clock += dt                          # the official clock, start line -> finish line

        for kind, group in SENSOR_GROUPS.items():
            self.sensor_timers[kind] += dt
            if self.sensor_timers[kind] >= group[0]["period"]:
                self.sensor_timers[kind] %= group[0]["period"]
                self._sense(physical_maze, kind)

        if self.motion == "AT_CENTER":
            self._plan_at_center()
        elif self.motion == "TURN":
            self._turn_step()
        elif self.motion == "ARC":
            self._arc_step()
        elif self.motion == "DIAG":
            self._diag_step(dt)
        else:
            self._drive_step(dt)
        if self.state != "EXPLORING":
            return
        if self.motion == "ARC":
            v_cmd, w_cmd = self.v, self._arc_omega()
        elif self.motion == "DIAG":
            v_cmd, w_cmd = self.v, self.steer
        else:
            v_cmd = self.v if self.motion == "DRIVE" else 0.0
            w_cmd = self.steer if self.motion == "DRIVE" else (self.omega if self.motion == "TURN" else 0.0)
        self._odometry(*self.body.step(v_cmd, w_cmd, dt))
        if self.body.crashed(self.sensors):
            self._finish_round(crashed=True)
            return
        self._check_timing_lines(physical_maze)
        if self.motion == "DRIVE":
            self.run["max_offset"] = max(self.run["max_offset"], abs(self.true_offset()))
        self.sensor_timer_trail = getattr(self, "sensor_timer_trail", 0) + 1
        if self.sensor_timer_trail % 4 == 0:
            self.true_trail.append((self.body.px, self.body.py, abs(self.body.wl + self.body.wr) / 2))
        self._track_cell()

    def _odometry(self, enc_dist, enc_turn):
        """Update the believed pose from what the wheel encoders measured this tick."""
        self.enc_rate = enc_turn
        if self.motion in ("ARC", "DIAG"):
            # off the lane grid: plain 2-D dead reckoning (the offset / heading estimates were folded
            # in); on the diagonal also the wheel curve the observer has learned
            curve = self.est_curve * enc_dist if self.motion == "DIAG" and DIAG_USE_CURVE else 0.0
            self.theta += enc_turn + curve
            self.px += math.cos(self.theta) * enc_dist
            self.py += math.sin(self.theta) * enc_dist
            self.pose_hist.append(self.believed_pose())
            return
        fx, fy = DIRECTIONS[self.heading]
        self.px += fx * enc_dist
        self.py += fy * enc_dist
        self.pose_hist.append(self.believed_pose())
        if self.motion == "TURN":
            self.theta += enc_turn
        else:
            # driving straight (or coasting to a stop): the observer tracks the small heading changes
            self.est_offset += enc_dist * math.sin(self.est_heading)
            self.est_heading += enc_turn + self.est_curve * enc_dist

    def believed_pose(self):
        """Where the firmware thinks it is: cell-line pose plus the observer's offset / heading."""
        fx, fy = DIRECTIONS[self.heading]
        return (self.px - fy * self.est_offset, self.py + fx * self.est_offset, self.theta + self.est_heading)

    def true_offset(self):
        """How far the REAL body is from the centre line of its cell (cm, + = right). Telemetry only."""
        fx, fy = DIRECTIONS[self.heading]
        cx = (int(self.body.px // CELL_SIZE_CM) + 0.5) * CELL_SIZE_CM
        cy = (int(self.body.py // CELL_SIZE_CM) + 0.5) * CELL_SIZE_CM
        return (self.body.px - cx) * -fy + (self.body.py - cy) * fx

    # ----------------------------------------------------------------- sensing
    def _pose_ago(self, seconds):
        """Where the firmware believed it was `seconds` ago."""
        return self.pose_hist[max(0, len(self.pose_hist) - 1 - round(seconds * PHYSICS_HZ))]

    def _sense(self, physical_maze, kind):
        """A new reading from every sensor of one kind (they finish their measurement together)."""
        if self.sensors is None or self.sensors.maze is not physical_maze:
            self.sensors = SensorArray(physical_maze)
        group = SENSOR_GROUPS[kind]
        latency = group[0]["latency"]
        new = self.sensors.scan(*self.body.pose_ago(latency), which=group)
        # a reading describes the pose `latency` ago: place it where we believed we were back then
        believed = [reading_at(*self._pose_ago(latency), r) for r in new]
        for r, b in zip(new, believed):
            self.latest[r.sensor["name"]] = (r, b)
        self.readings = [self.latest[s["name"]][0] for s in SENSORS if s["name"] in self.latest]
        self.believed_readings = [self.latest[s["name"]][1] for s in SENSORS if s["name"] in self.latest]
        changed = False
        if self.motion in ("DRIVE", "AT_CENTER"):
            # while rotating (corners, pivots) the believed beam directions are least certain and an
            # old reading can point several degrees off: don't let those readings edit the map
            for r in believed:
                changed |= self.mapper.add_reading(r)
        if changed:
            self.flood = self._flood(optimistic=True)
            self.known_view = None                        # the firmware's wall model changed
        self.walls_seen = False
        if self.motion == "DRIVE":
            self._observe_walls(believed)
        elif self.motion == "DIAG":
            self._observe_2d(believed)
        elif self.motion == "AT_CENTER" and kind == FRONT_TOF["kind"]:
            front = next(r for r in new if r.sensor is FRONT_TOF)
            if front.distance is not None:
                self.front_samples.append(front.distance)

    # --------------------------------------------------------------- centering
    def _observe_walls(self, readings):
        """Correct the pose estimate with every reading the mouse's own map can explain.

        Each TOF distance is compared with what it SHOULD read, ray-cast from the believed pose
        (at the moment of the reading) against the walls the mouse has confirmed:
          * hit a wall running along the lane  -> the difference is sideways error:
            z = offset + y_hit * heading, so it corrects offset, heading and the wheel curve;
          * hit a wall across the lane (e.g. the front wall) -> the difference is how far
            along the lane the mouse really is;
          * hit a post, nothing known, or far off the prediction -> not trusted, skipped.
        The short-range IR can only see something right beside the body, so it is used directly.
        """
        if self.known_view is None:
            self.known_view = SensorArray(self.memory, known_only=True)
        fx, fy = DIRECTIONS[self.heading]
        rx, ry = -fy, fx
        for r in readings:
            s = r.sensor
            if r.distance is None:
                continue
            if s["kind"] == "IR":
                sin_a = math.sin(math.radians(s["angle"]))
                side = 1 if sin_a > 0 else -1
                z = side * (WALL_FACE - side * s["x"] - r.distance * abs(sin_a))
                self._correct_sideways(z - (self.est_offset + s["y"] * self.est_heading), 6.0)
                continue
            if r.distance > MAP_TRUST_CM:
                continue
            (ox, oy), (dx, dy) = r.origin, r.direction
            hit = self.known_view.first_hit(ox, oy, dx, dy, r.distance + 6.0)
            if hit is None or hit[1] == 'post':
                continue
            t_pred, kind, _ = hit
            innovation = r.distance - t_pred              # + = the wall is further than expected
            if abs(innovation) > 3.0:
                continue
            if (kind == 'V') == (fx == 0):                # a wall running along the lane
                u_side = dx * rx + dy * ry                # beam's sideways component (+ = right)
                if abs(u_side) > 0.5:
                    self._correct_sideways(-innovation * u_side, 3.0)
            else:                                         # a wall across the lane
                u_fwd = dx * fx + dy * fy
                if abs(u_fwd) > 0.5:
                    shift = -ALONG_GAIN * innovation * u_fwd
                    self.px += fx * shift
                    self.py += fy * shift

    def _correct_sideways(self, err, gate):
        """One observer update from a sideways error: measured minus predicted offset (cm)."""
        if abs(err) > gate:
            return                                        # outlier (post corner, noise spike)
        self.est_offset += OBS_K_OFFSET * err
        self.est_heading += OBS_K_HEADING * err
        self.est_curve = max(-MAX_CURVE, min(MAX_CURVE, self.est_curve + OBS_K_CURVE * err))
        self.walls_seen = True

    def _steer(self):
        """Steering law, every physics tick while driving straight.

        The observer predicts offset' = v * heading and heading' = (encoder turn rate) +
        curve * v (curve = the wheel-size mismatch it has learned) in _odometry. Steer:
        pull offset and heading to zero and cancel the learned curve - this keeps
        working where there are no walls.
        """
        steer = -(CENTER_KP * self.est_offset + CENTER_KH * self.est_heading) - self.est_curve * self.v
        self.steer = max(-MAX_STEER_RAD_S, min(MAX_STEER_RAD_S, steer))

    def _track_cell(self):
        """Notice when the body centre crosses into a new cell."""
        cx = min(COLS - 1, max(0, int(self.px // CELL_SIZE_CM)))
        cy = min(ROWS - 1, max(0, int(self.py // CELL_SIZE_CM)))
        if (cx, cy) == (self.x, self.y):
            return
        for d, (dx, dy) in DIRECTIONS.items():
            if (self.x + dx, self.y + dy) == (cx, cy):
                if self.mapper.mark_driven(self.x, self.y, d):
                    self.flood = self._flood(optimistic=True)
                break
        self.x, self.y = cx, cy
        self.memory.grid[cx][cy].discovered = True
        self.round_visited.add((cx, cy))
        self.global_visited.add((cx, cy))
        self.path_stack.append((cx, cy))
        self.run["cells"] += 1

    # ------------------------------------------------------------------ motion
    def _plan_at_center(self):
        if not self.calibrated and self._front_wall_recenter():
            return
        if (self.x, self.y) in self.nav_cells:
            if self.phase == "TO_GOAL":
                if not AUTO_RETURN:
                    self._finish_round()                  # reached the goal: the operator carries it back
                    return
                self._start_return()                      # ... or it drives itself home
                return
            if not self._park_at_start():                 # home: line up for the next run
                return
            self._finish_round()
            return
        step = self._choose_step(self.x, self.y, self.heading)
        if step is None:                        # fully walled in (invalid maze)
            self._finish_round()
            return
        d, nx, ny = step
        if d != self.heading:
            self.turn_to = d
            self.motion = "TURN"
        elif self._edge_known_open(self.x, self.y, d):
            self.target, self.decided = (nx, ny), False
            self.motion = "DRIVE"
        # else: wait here - the front sensor is still confirming the edge ahead

    def _start_return(self):
        """The run is scored; now drive back to the start (untimed) to line up for the next one.
        On the way the mouse keeps mapping, so a search run also explores on the way home."""
        self.phase = "TO_START"
        self.nav_cells = {self.start}
        self.flood = self._flood(optimistic=True)

    def _park_at_start(self):
        """Back in the start cell: face North and reverse to the flying-start spot. True when done."""
        if self.heading != START_OPENING:
            self.turn_to = START_OPENING
            self.motion = "TURN"
            return False
        if not self.parked:
            # tell the controller we are START_BACKOFF_CM past the centre: it reverses that far
            fx, fy = DIRECTIONS[self.heading]
            self.px += fx * START_BACKOFF_CM
            self.py += fy * START_BACKOFF_CM
            self.target, self.decided, self.recentering = self.start, True, True
            self.motion = "DRIVE"
            self.parked = True
            return False
        return True

    def _turn_step(self):
        # the firmware measures its turn with the wheel encoders
        dt = 1.0 / PHYSICS_HZ
        goal = HEADING_ANGLE[self.turn_to]
        err = _wrap(goal - self.theta)
        if not self.turn_settling:
            w_des = math.copysign(min(MAX_TURN_RAD_S, math.sqrt(2 * TURN_ACCEL_RAD_S2 * abs(err))), err)
            self.omega = _approach(self.omega, w_des, TURN_ACCEL_RAD_S2 * dt)
            if abs(err) < math.radians(0.5) or err * self.omega < 0:
                self.omega, self.turn_settling = 0.0, True   # stop commanding; the motors still coast
        elif abs(self.enc_rate) < 1e-4:
            # wheels stopped: whatever over/undershoot the encoders saw becomes a heading error
            self.turn_settling = False
            self.est_heading = _wrap(self.est_heading + self.theta - goal)
            self.theta = goal
            self.heading = self.turn_to
            self.motion = "AT_CENTER"
            self.front_samples, self.calibrated = [], False  # re-centre on the wall now in front
            self.est_offset = 0.0                            # old along-error is the new offset: unknown

    def _drive_step(self, dt):
        fx, fy = DIRECTIONS[self.heading]
        tx, ty = cell_center(*self.target)
        d_rem = (tx - self.px) * fx + (ty - self.py) * fy

        if not self.decided and d_rem <= self._decision_distance():
            self._decide_after_target()
            tx, ty = cell_center(*self.target)
            d_rem = (tx - self.px) * fx + (ty - self.py) * fy

        # speed profile: never faster than what still lets us stop at the target centre - or,
        # when a smooth turn is planned there, reach its entry edge at the turn speed
        v_max = self._speed_limit()
        v_end = 0.0
        if self.pending:
            sx, sy = self.pending["start"]
            d_rem = (sx - self.px) * fx + (sy - self.py) * fy   # distance to where the arc starts
            v_end = self.pending["speed"]
            if d_rem <= self.v * MOTOR_LAG_COMP_S:          # start early: the motors lag
                self._begin_arc(self.pending)
                return
        v_des = math.copysign(min(v_max, math.sqrt(v_end ** 2 + 2 * ACCEL_CM_S2 * abs(d_rem))), d_rem)
        self.v = _approach(self.v, v_des, ACCEL_CM_S2 * dt)
        step = self.v * dt
        if self.decided and not self.pending and (
                abs(d_rem) < 0.05 or (abs(step) >= abs(d_rem) and abs(self.v) < 5)):
            self.px, self.py, self.v = tx, ty, 0.0          # encoders say: arrived on the centre
            self.motion = "AT_CENTER"
            self.front_samples, self.steer = [], 0.0
            self.calibrated = self.recentering              # a re-centre move doesn't re-centre again
            self.recentering = False
            return
        self._steer()

    def _front_wall_recenter(self):
        """Stopped facing a known wall: average the front TOF and fix the along-cell position.

        Returns True while busy (collecting samples or driving the small correction).
        """
        cell = self.memory.grid[self.x][self.y]
        if not (cell.walls_known[self.heading] and cell.walls[self.heading]):
            self.calibrated = True
            return False
        if len(self.front_samples) < FRONT_SAMPLES:
            return True                                   # wait a few sensor ticks
        self.calibrated = True
        expected = WALL_FACE - FRONT_TOF["y"]             # sensor -> wall face when centred
        err = sum(self.front_samples[-FRONT_SAMPLES:]) / FRONT_SAMPLES - expected
        if abs(err) < 0.5 or abs(err) > 5.0:
            return False
        fx, fy = DIRECTIONS[self.heading]
        self.px -= fx * err                               # we are really `err` cm short of the centre
        self.py -= fy * err
        self.target, self.decided, self.recentering = (self.x, self.y), True, True
        self.motion = "DRIVE"
        return True

    def _turn_speed(self):
        corner = FAST_TURN_SPEED_CM_S if self.mode == "FAST" else SEARCH_TURN_SPEED_CM_S
        return min(corner, self._speed_limit())

    def _speed_limit(self):
        """Full motor speed (381 rpm) on fast runs and through cells already mapped; slower only
        when heading into a cell whose walls are not all confirmed yet."""
        if self.phase == "TO_START":
            return HOME_SPEED_CM_S
        if self.mode == "FAST":
            return MAX_SPEED_CM_S
        cell = self.memory.grid[self.target[0]][self.target[1]]
        return SEARCH_SPEED_CM_S if all(cell.walls_known.values()) else EXPLORE_SPEED_CM_S

    def _decision_distance(self):
        """How far before the target centre the next move must be decided: early enough to stop
        at the centre, and early enough to slow down to the turn speed before a corner."""
        stop = self.v ** 2 / (2 * ACCEL_CM_S2)
        lead = TURN_RADIUS_CM                              # how far before the centre an arc can start
        if self.mode == "FAST" and self.plan:
            lead = max(lead, BIG_TURN_RADIUS_CM, TURN_RADIUS_CM + DIAG_TURN_RADIUS_CM * math.tan(math.pi / 8))
        corner = lead + max(0.0, self.v ** 2 - self._turn_speed() ** 2) / (2 * ACCEL_CM_S2)
        return max(stop, corner) + DECISION_MARGIN_CM

    def _decide_after_target(self):
        """Approaching the target cell: straight through it, a smooth turn in it, or stop there?"""
        self.decided = True
        self.pending = None
        tx, ty = self.target
        if (tx, ty) in self.nav_cells:
            if self.phase != "TO_GOAL":
                return                                    # stop in the start cell
            # the finish line is the goal ENTRANCE, so don't brake for it: cross at full speed and
            # use the room behind it to stop (rule 6.1.f)
            fx, fy = DIRECTIONS[self.heading]
            deeper = (tx + fx, ty + fy)
            if deeper in self.target_cells and not (self.memory.grid[tx][ty].walls_known[self.heading]
                                                    and self.memory.grid[tx][ty].walls[self.heading]):
                self.target = deeper
            return                                            # ... then stop inside the goal
        step = self._choose_step(tx, ty, self.heading)
        if not step:
            return
        d = step[0]
        if not self._edge_known_open(tx, ty, d):
            return                                            # not sure yet: stop and look
        if d == self.heading:
            self.target, self.decided = (step[1], step[2]), False
            return
        special = self.plan.get((tx, ty)) if self.mode == "FAST" and self.phase == "TO_GOAL" else None
        if special and special[0] == "diag":
            self.pending = self._diagonal_plan(special[1])    # cut the staircase diagonally
        elif d in (LEFT_OF[self.heading], RIGHT_OF[self.heading]):
            radius = BIG_TURN_RADIUS_CM if special else TURN_RADIUS_CM
            self.pending = self._corner_plan((tx, ty), self.heading, d, radius)   # corner without stopping

    # ------------------------------------------------------------- arcs & diagonals
    def _corner_plan(self, cell, h, d, radius):
        """A quarter circle turning from lane h to lane d around corner `cell`, tangent to both
        lane centre lines: radius half a cell = centred on the corner post (edge middle to edge
        middle); bigger radii start earlier and finish later but are faster."""
        cx, cy = cell_center(*cell)
        hx, hy = DIRECTIONS[h]
        dx, dy = DIRECTIONS[d]
        return {"start": (cx - hx * radius, cy - hy * radius), "radius": radius,
                "center": (cx + (dx - hx) * radius, cy + (dy - hy) * radius),
                "side": 1 if d == RIGHT_OF[h] else -1, "sweep": math.pi / 2,
                "speed": self._turn_speed() if radius == TURN_RADIUS_CM else corner_speed(radius),
                "then": ("lane", d, (cell[0] + dx, cell[1] + dy), cell)}

    def _curve_45(self, vertex, u_in, u_out, then):
        """A 45-degree curve of DIAG_TURN_RADIUS_CM between two straight lines meeting at `vertex`."""
        r = DIAG_TURN_RADIUS_CM
        tangent = r * math.tan(math.pi / 8)
        side = 1 if u_in[0] * u_out[1] - u_in[1] * u_out[0] > 0 else -1     # + = clockwise (right)
        start = (vertex[0] - u_in[0] * tangent, vertex[1] - u_in[1] * tangent)
        right = (-u_in[1], u_in[0])
        return {"start": start, "radius": r, "side": side, "sweep": math.pi / 4,
                "center": (start[0] + side * right[0] * r, start[1] + side * right[1] * r),
                "speed": corner_speed(r), "then": then}

    def _diagonal_plan(self, stair):
        """Staircase cells [(cell, in, out), ...] -> curve onto a 45-degree line through the middles
        of their edges, run it straight, curve back into the lane after the last one."""
        (c1, h, d1), (ck, _, dk) = stair[0], stair[-1]
        hx, hy = DIRECTIONS[h]
        x1, y1 = cell_center(*c1)
        xk, yk = cell_center(*ck)
        m0 = (x1 - hx * TURN_RADIUS_CM, y1 - hy * TURN_RADIUS_CM)                  # entry edge middle
        mk = (xk + DIRECTIONS[dk][0] * TURN_RADIUS_CM, yk + DIRECTIONS[dk][1] * TURN_RADIUS_CM)
        length = math.hypot(mk[0] - m0[0], mk[1] - m0[1])
        u = ((mk[0] - m0[0]) / length, (mk[1] - m0[1]) / length)
        tangent = DIAG_TURN_RADIUS_CM * math.tan(math.pi / 8)
        exit_curve = self._curve_45(mk, u, DIRECTIONS[dk],
                                    ("lane", dk, (ck[0] + DIRECTIONS[dk][0], ck[1] + DIRECTIONS[dk][1]), ck))
        line = {"start": (m0[0] + u[0] * tangent, m0[1] + u[1] * tangent), "u": u,
                "length": length - 2 * tangent, "exit": exit_curve}
        return self._curve_45(m0, (hx, hy), u, ("diag", line))

    def _plan_fast_path(self):
        """Walk the fast route once and mark the cells where faster geometry fits:
          * a staircase (2+ corners in a row alternating left/right, straight before and after)
            -> a diagonal;
          * a lone corner with straights on both sides -> a big corner."""
        order, cell, h, seen = [], self.start, START_OPENING, set()
        while cell in self.route and cell not in seen:
            seen.add(cell)
            d = self.route[cell]
            order.append((cell, h, d))
            cell, h = (cell[0] + DIRECTIONS[d][0], cell[1] + DIRECTIONS[d][1]), d
        corner = [h != d and d != OPPOSITE[h] for _, h, d in order]
        side = [1 if d == RIGHT_OF[h] else -1 for _, h, d in order]
        plan, i = {}, 0
        while i < len(order):
            if corner[i] and DIAGONALS and not (DIAG_HERO_ONLY and self.hero_done):
                j = i + 1
                while j < len(order) and corner[j] and side[j] == -side[j - 1]:
                    j += 1
                if j - i >= 2 and not corner[i - 1] and (j == len(order) or not corner[j]):
                    plan[order[i][0]] = ("diag", order[i:j])
                    i = j
                    continue
            if (corner[i] and BIG_CORNERS and not corner[i - 1]
                    and (i + 1 == len(order) or not corner[i + 1])):
                plan[order[i][0]] = ("big",)
            i += 1
        return plan

    def _begin_arc(self, plan):
        """At the arc's start point: fold the offset / heading estimates into the pose and go."""
        self.px, self.py, self.theta = self.believed_pose()
        self.est_offset = self.est_heading = 0.0
        self.arc = dict(plan)
        ox, oy = plan["center"]
        sx, sy = plan["start"]
        self.arc["phi0"] = math.atan2(sy - oy, sx - ox)
        self.v = min(plan["speed"], self._speed_limit())
        self.pending = None
        self.motion = "ARC"

    def _arc_progress(self):
        """How far round the arc the (believed) position is, in radians."""
        ox, oy = self.arc["center"]
        return self.arc["side"] * _wrap(math.atan2(self.py - oy, self.px - ox) - self.arc["phi0"])

    def _arc_omega(self):
        """Follow the ideal arc: nominal curvature, plus corrections for being off the circle
        or off its tangent (from the encoder dead reckoning)."""
        ox, oy = self.arc["center"]
        r, side = self.arc["radius"], self.arc["side"]
        radial = math.hypot(self.px - ox, self.py - oy) - r                     # + = outside the arc
        tangent = math.atan2(self.py - oy, self.px - ox) + side * math.pi / 2
        w = side * self.v / r + side * ARC_K_RADIUS * radial - ARC_K_HEADING * _wrap(self.theta - tangent)
        return max(-MAX_TURN_RAD_S, min(MAX_TURN_RAD_S, w))

    def _arc_step(self):
        """Finish the arc - a little early, because the motors keep turning a moment."""
        if self._arc_progress() < self.arc["sweep"] - (self.v / self.arc["radius"]) * MOTOR_LAG_COMP_S:
            return
        then = self.arc["then"]
        if then[0] == "diag":
            self.diag = then[1]
            self.motion = "DIAG"
            return
        _, new, next_cell, lane_cell = then
        ex, ey = cell_center(*lane_cell)                     # a cell on the new lane's centre line
        self.heading = new
        # re-express the dead-reckoned pose in the new lane: along -> px/py, the rest -> estimates
        fx, fy = DIRECTIONS[new]
        rx, ry = -fy, fx
        lateral = (self.px - ex) * rx + (self.py - ey) * ry
        self.px -= rx * lateral
        self.py -= ry * lateral
        self.est_offset = lateral
        self.est_heading = _wrap(self.theta - HEADING_ANGLE[new])
        self.theta = HEADING_ANGLE[new]
        self.target, self.decided = next_cell, False
        self.motion = "DRIVE"

    def _diag_step(self, dt):
        """Straight along the diagonal line, steering onto it from the 2-D dead-reckoned pose."""
        line = self.diag
        (bx, by), (ux, uy) = line["start"], line["u"]
        remaining = line["length"] - ((self.px - bx) * ux + (self.py - by) * uy)
        if remaining <= self.v * MOTOR_LAG_COMP_S:
            self._begin_arc(line["exit"])
            return
        v_des = min(DIAG_SPEED_CM_S, math.sqrt(line["exit"]["speed"] ** 2 + 2 * ACCEL_CM_S2 * max(0.0, remaining)))
        self.v = _approach(self.v, v_des, ACCEL_CM_S2 * dt)
        lateral = -(self.px - bx) * uy + (self.py - by) * ux                   # + = right of the line
        heading_err = _wrap(self.theta - math.atan2(uy, ux))
        steer = -(DIAG_KP * lateral + DIAG_KH * heading_err) - (self.est_curve * self.v if DIAG_USE_CURVE else 0.0)
        self.steer = max(-MAX_STEER_RAD_S, min(MAX_STEER_RAD_S, steer))

    def _observe_2d(self, readings):
        """On the diagonal there are no lane walls to centre on: fix the 2-D position from every
        reading the mouse's map can explain - any known wall OR post face (posts are always there)."""
        if self.known_view is None:
            self.known_view = SensorArray(self.memory, known_only=True)
        for r in readings:
            if r.distance is None or r.distance > MAP_TRUST_CM:
                continue
            (ox, oy), (dx, dy) = r.origin, r.direction
            hit = self.known_view.first_hit(ox, oy, dx, dy, r.distance + 6.0)
            if hit is None:
                continue
            t_pred, _, axis = hit
            innovation = r.distance - t_pred              # + = the surface is further than expected
            component = dx if axis == 'x' else dy
            if abs(innovation) > 3.0 or abs(component) < 0.3:
                continue
            shift = -DIAG_POS_GAIN * innovation * component
            sx, sy = (shift, 0.0) if axis == 'x' else (0.0, shift)
            self.px += sx
            self.py += sy
            # being pushed sideways off the line again and again means the heading is off too
            ux, uy = self.diag["u"]
            self.theta += DIAG_HEAD_GAIN * (-sx * uy + sy * ux)

    # ------------------------------------------------------------- flood fill
    def _edge_open(self, x, y, d, optimistic):
        """Can the mouse travel from (x, y) through edge d?"""
        cell = self.memory.grid[x][y]
        if optimistic:
            # open unless we have positively confirmed a wall
            return not (cell.walls_known[d] and cell.walls[d])
        # pessimistic: only edges we have confirmed to be open
        return cell.walls_known[d] and not cell.walls[d]

    def _edge_known_open(self, x, y, d):
        return self._edge_open(x, y, d, optimistic=False)

    def _flood(self, optimistic, goals=None):
        """BFS distance-to-nearest-goal for every cell (None = unreachable).

        `goals` defaults to wherever the mouse is heading now: the centre on the way out,
        the start cell on the way back.
        """
        dist = [[None] * ROWS for _ in range(COLS)]
        q = deque()
        for gx, gy in (goals if goals is not None else self.nav_cells):
            dist[gx][gy] = 0
            q.append((gx, gy))

        while q:
            x, y = q.popleft()
            for d, (dx, dy) in DIRECTIONS.items():
                nx, ny = x + dx, y + dy
                if not (0 <= nx < COLS and 0 <= ny < ROWS):
                    continue
                if dist[nx][ny] is not None:
                    continue
                if self._edge_open(x, y, d, optimistic):
                    dist[nx][ny] = dist[x][y] + 1
                    q.append((nx, ny))
        return dist

    # --------------------------------------------------------- move selection
    def _fast_route(self):
        """Quickest route start -> goal through confirmed-open edges, as {cell: direction}.

        Dijkstra over (cell, heading): each cell costs CELL_TIME, each turn TURN_TIME.
        """
        start = (*self.start, 'N')
        best, parent = {start: 0.0}, {start: None}
        pq = [(0.0, start)]
        while pq:
            cost, state = heapq.heappop(pq)
            x, y, h = state
            if cost > best[state]:
                continue
            if (x, y) in self.target_cells:
                route = {}
                while parent[state] is not None:
                    prev = parent[state]
                    route[prev[:2]] = state[2]
                    state = prev
                return route
            for d, (dx, dy) in DIRECTIONS.items():
                if not self._edge_known_open(x, y, d):
                    continue
                turn = 0 if d == h else (PIVOT_TIME if d == OPPOSITE[h] else TURN_TIME)
                nstate, ncost = (x + dx, y + dy, d), cost + CELL_TIME + turn
                if ncost < best.get(nstate, math.inf):
                    best[nstate], parent[nstate] = ncost, state
                    heapq.heappush(pq, (ncost, nstate))
        return {}

    def _choose_step(self, x, y, heading):
        if self.phase != "TO_GOAL":
            pass                                          # on the way home: plain flood fill
        elif self.mode == "FAST" and (x, y) in self.route and not self._edge_known_open(x, y, self.route[(x, y)]):
            self.route = self._fast_route()             # the map changed under the route: re-plan
            if not self.route:
                self.mode = self.run["mode"] = "SEARCH"
        if self.phase == "TO_GOAL" and self.mode == "FAST" and (x, y) in self.route:
            d = self.route[(x, y)]
            return d, x + DIRECTIONS[d][0], y + DIRECTIONS[d][1]
        best_key = None
        best_move = None

        for d, (dx, dy) in DIRECTIONS.items():
            if not self._edge_open(x, y, d, optimistic=True):
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < COLS and 0 <= ny < ROWS):
                continue
            fval = self.flood[nx][ny]
            if fval is None:
                continue

            if d == heading:
                turn_cost = 0
            elif d == OPPOSITE[heading]:
                turn_cost = 2
            else:
                turn_cost = 1
            explore_bonus = 0 if (nx, ny) in self.round_visited else -1

            key = (fval, turn_cost, explore_bonus, list(DIRECTIONS).index(d))
            if best_key is None or key < best_key:
                best_key = key
                best_move = (d, nx, ny)

        return best_move

    # -------------------------------------------------------------- end of a run
    def _finish_round(self, crashed=False):
        """A run is over: it reached the goal, crashed, or is boxed in. The operator picks it up."""
        self.v = self.omega = 0.0
        self.run["crashed"] = crashed
        self.run["diagonal"] = any(v[0] == "diag" for v in self.plan.values()) if self.mode == "FAST" else False
        if self.run["diagonal"] and self.run["time"] is not None:
            self.hero_done = True                         # the fast diagonal time is banked
        self.run["returned"] = not crashed and self.phase == "TO_START"
        # solved_optimally: the confirmed best route is already as short as the optimistic lower
        # bound, so more exploring cannot improve it - from here on the mouse races.
        confirmed = self._flood(optimistic=False, goals=self.target_cells)
        optimistic = self._flood(optimistic=True, goals=self.target_cells)
        sx, sy = self.start
        if confirmed[sx][sy] is not None and confirmed[sx][sy] == optimistic[sx][sy]:
            self.solved_optimally = True
        self.state = "RUN_OVER"
