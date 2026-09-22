# micromouse.py
import heapq
import math
import random
from collections import deque
from maze import Maze
from mapper import Mapper
from sensors import SensorArray, reading_at
from body import RobotBody
from config import (PHYSICS_HZ, SENSOR_LATENCY_S, COLS, ROWS, DIRECTIONS, OPPOSITE, TARGET_CELLS, START_CELL, CELL_SIZE_CM,
                    WALL_THICKNESS_CM, SENSORS, SENSOR_HZ, MAX_SPEED_CM_S, SEARCH_SPEED_CM_S, ACCEL_CM_S2,
                    MAX_TURN_RAD_S, TURN_ACCEL_RAD_S2, WHEEL_MISMATCH, START_POS_ERROR_CM,
                    START_ANGLE_ERROR_DEG, CENTER_KP, CENTER_KH, MAX_STEER_RAD_S,
                    OBS_K_OFFSET, OBS_K_HEADING, OBS_K_CURVE)

# Heading angle of each compass direction (world y axis points down, so North = -90 deg)
HEADING_ANGLE = {'E': 0.0, 'S': math.pi / 2, 'W': math.pi, 'N': -math.pi / 2}
# Time costs used to pick the quickest fast-run route
CELL_TIME = CELL_SIZE_CM / MAX_SPEED_CM_S
TURN_TIME = MAX_SPEED_CM_S / ACCEL_CM_S2 + 2 * math.sqrt((math.pi / 2) / TURN_ACCEL_RAD_S2)  # brake + turn + re-accelerate
DECISION_MARGIN_CM = 1.0        # decide the next move this far before the braking point
WALL_FACE = CELL_SIZE_CM / 2 - WALL_THICKNESS_CM / 2    # centre line -> wall face (8.4 cm)
LEFT_OF = {'N': 'W', 'E': 'N', 'S': 'E', 'W': 'S'}
RIGHT_OF = {v: OPPOSITE[k] for k, v in LEFT_OF.items()}
FRONT_TOF = next(s for s in SENSORS if s["kind"] == "TOF" and s["angle"] == 0)
FRONT_SAMPLES = 4               # front-wall readings averaged before re-centring at a stop
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

      1. SENSE  - at SENSOR_HZ, reads its 5 sensors (2 side IR + 3 TOF, see
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
        self.max_rounds = 3
        self.target_cells = set(TARGET_CELLS)
        self.start = START_CELL
        self.reset_all()

    # ------------------------------------------------------------------ setup
    def reset_all(self):
        self.memory = Maze(is_blank_memory=True)
        self.mapper = Mapper(self.memory)
        self.sensors = None                     # built lazily against the physical maze
        self.round_steps = [0, 0, 0]            # cells entered per round
        self.round_times = [0.0, 0.0, 0.0]      # seconds per round
        self.max_offset = [0.0, 0.0, 0.0]       # telemetry: worst real off-centre while driving, cm
        self.round_modes = ["SEARCH", None, None]
        self.mode = "SEARCH"
        self.route = {}                         # FAST mode: cell -> direction to drive
        self.current_round = 1
        self.state = "IDLE"
        self.solved_optimally = False
        self.global_visited = set([self.start])
        # this robot's wheels: a fixed small size mismatch the firmware doesn't know about
        self.wheel_gain = (1 + random.gauss(0, WHEEL_MISMATCH), 1 + random.gauss(0, WHEEL_MISMATCH))
        self.est_curve = 0.0                    # firmware: learned curve from that mismatch (rad per cm)
        self._place_at_start()
        self.flood = self._flood(optimistic=True)

    def _place_at_start(self):
        """Set the mouse down (by hand) in the centre of the start cell, facing north."""
        self.x, self.y = self.start
        self.px, self.py = cell_center(*self.start)
        self.heading = 'N'
        self.theta = HEADING_ANGLE['N']
        self.v = 0.0                            # forward speed, cm/s
        self.omega = 0.0                        # turn rate, rad/s
        self.motion = "AT_CENTER"               # AT_CENTER | TURN | DRIVE
        self.target = self.start                # cell centre the mouse is braking towards
        self.decided = True                     # has the move after `target` been decided?
        self.turn_to = None
        self.path_stack = [self.start]          # actual trajectory this round
        self.round_visited = set([self.start])
        self.sensor_timer = 1.0 / SENSOR_HZ     # read the sensors on the first tick
        self.readings = []                      # what the sensors report (from the TRUE pose)
        self.believed_readings = []             # the same distances placed at the BELIEVED pose
        self.steer = 0.0                        # centering correction, rad/s
        self.est_offset = 0.0                   # observer: cm right of the centre line
        self.est_heading = 0.0                  # observer: rad clockwise of the heading
        self.walls_seen = False                 # did a side wall correct the observer this tick?
        self.turn_settling = False
        self.enc_rate = 0.0                     # encoder turn this tick (rad)
        self.true_trail = []                    # telemetry: where the REAL body went this round
        self.pose_hist = deque([(self.px, self.py, self.theta)],
                               maxlen=max(1, round(SENSOR_LATENCY_S * PHYSICS_HZ)) + 1)
        self.front_samples = []
        self.calibrated = False                 # front-wall re-centre done at this stop?
        self.recentering = False
        # the real body: set down by hand, never exactly on the centre or exactly straight
        err = START_POS_ERROR_CM
        self.body = RobotBody(self.px + random.uniform(-err, err), self.py + random.uniform(-err, err),
                              self.theta + math.radians(random.uniform(-START_ANGLE_ERROR_DEG, START_ANGLE_ERROR_DEG)),
                              self.wheel_gain)
        self.memory.grid[self.x][self.y].discovered = True

    def next_round_mode(self):
        if self.solved_optimally or self.current_round + 1 == self.max_rounds:
            return "FAST"
        return "SEARCH"

    def start_next_round(self):
        self.mode = self.next_round_mode()
        self.current_round += 1
        self._place_at_start()
        self.route = self._fast_route() if self.mode == "FAST" else {}
        if not self.route:
            self.mode = "SEARCH"                # no confirmed route yet: keep exploring
        self.round_modes[self.current_round - 1] = self.mode
        self.global_visited.add(self.start)
        self.state = "EXPLORING"
        self.flood = self._flood(optimistic=True)

    # -------------------------------------------------------------- main tick
    def update(self, physical_maze, dt):
        if self.state != "EXPLORING":
            return
        self.round_times[self.current_round - 1] += dt

        self.sensor_timer += dt
        if self.sensor_timer >= 1.0 / SENSOR_HZ:
            self.sensor_timer %= 1.0 / SENSOR_HZ
            self._sense(physical_maze)

        if self.motion == "AT_CENTER":
            self._plan_at_center()
        elif self.motion == "TURN":
            self._turn_step()
        else:
            self._drive_step(dt)
        if self.state != "EXPLORING":
            return
        v_cmd = self.v if self.motion == "DRIVE" else 0.0
        w_cmd = self.steer if self.motion == "DRIVE" else (self.omega if self.motion == "TURN" else 0.0)
        self._odometry(*self.body.step(v_cmd, w_cmd, dt))
        if self.body.crashed(self.sensors):
            self._finish_round(crashed=True)
            return
        if self.motion == "DRIVE":
            off = abs(self.true_offset())
            self.max_offset[self.current_round - 1] = max(self.max_offset[self.current_round - 1], off)
        self.sensor_timer_trail = getattr(self, "sensor_timer_trail", 0) + 1
        if self.sensor_timer_trail % 8 == 0:
            self.true_trail.append((self.body.px, self.body.py))
        self._track_cell()

    def _odometry(self, enc_dist, enc_turn):
        """Update the believed pose from what the wheel encoders measured this tick."""
        fx, fy = DIRECTIONS[self.heading]
        self.px += fx * enc_dist
        self.py += fy * enc_dist
        self.enc_rate = enc_turn
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
    def _sense(self, physical_maze):
        if self.sensors is None or self.sensors.maze is not physical_maze:
            self.sensors = SensorArray(physical_maze)
        self.readings = self.sensors.scan(*self.body.sensed_pose())
        # the readings are SENSOR_LATENCY_S old: place them where we believed we were back then
        self.believed_readings = [reading_at(*self.pose_hist[0], r) for r in self.readings]
        changed = False
        for r in self.believed_readings:
            changed |= self.mapper.add_reading(r)
        if changed:
            self.flood = self._flood(optimistic=True)
        self.walls_seen = False
        if self.motion == "DRIVE":
            self._observe_walls()
        elif self.motion == "AT_CENTER":
            front = next(r for r in self.readings if r.sensor is FRONT_TOF)
            if front.distance is not None:
                self.front_samples.append(front.distance)

    # --------------------------------------------------------------- centering
    def _observe_walls(self):
        """Correct the observer with every side-wall reading.

        A side-looking sensor (mount sx, sy, angle a) hitting a side wall gives
        z = side * (WALL_FACE - side*sx - d*|sin a|). For small heading errors that is
        z = offset + y_hit * heading, where y_hit is how far ahead of the body centre
        the beam lands - so the observer sees offset and heading mixed with a known lever.
        """
        for r in self.readings:
            s = r.sensor
            sin_a = math.sin(math.radians(s["angle"]))
            if r.distance is None or abs(sin_a) < 0.5:
                continue
            side = 1 if sin_a > 0 else -1
            cos_a = math.cos(math.radians(s["angle"]))
            y_hit = s["y"] + r.distance * cos_a
            # the 2.5 cm IR can only be seeing something right beside the body (wall or flush post);
            # the long diagonal TOFs must land on a wall the map already knows
            if s["kind"] != "IR":
                if not self._side_wall_at(side, y_hit):
                    continue                             # beam isn't on a known side wall
                if cos_a > 0.1 and self._front_wall_first(s, side, sin_a, cos_a):
                    continue                             # the wall across the lane could catch it first
            z = side * (WALL_FACE - side * s["x"] - r.distance * abs(sin_a))
            err = z - (self.est_offset + y_hit * self.est_heading)
            if abs(err) > (6.0 if s["kind"] == "IR" else 3.0):
                continue      # outlier (post corner, noise spike); the short-range IR is trusted further
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

    def _front_wall_first(self, s, side, sin_a, cos_a):
        """Could a forward-looking diagonal hit the wall ACROSS the lane before (or about when)
        it reaches the side wall? Then the reading isn't a clean side-wall distance."""
        d_side = (WALL_FACE - side * s["x"] - side * self.est_offset) / abs(sin_a)
        fx, fy = DIRECTIONS[self.heading]
        ahead = s["y"] + d_side * cos_a
        ax, ay = self.px + fx * ahead, self.py + fy * ahead
        cx, cy = int(ax // CELL_SIZE_CM), int(ay // CELL_SIZE_CM)
        if not (0 <= cx < COLS and 0 <= cy < ROWS):
            return True
        lane = self.memory.grid[cx][cy]
        if lane.walls_known[self.heading] and not lane.walls[self.heading]:
            return False                                  # that cross wall is known to be absent
        # distance from the body centre to the face of the wall across that cell
        into = (ax * fx + ay * fy) % CELL_SIZE_CM
        front_face = ahead + (CELL_SIZE_CM - into) - WALL_THICKNESS_CM / 2
        d_front = (front_face - s["y"]) / cos_a
        return d_front < d_side + 1.5

    def _side_wall_at(self, side, ahead):
        """Is there a known wall on this side (+1 right, -1 left), `ahead` cm in front of the body centre?"""
        fx, fy = DIRECTIONS[self.heading]
        ax, ay = self.px + fx * ahead, self.py + fy * ahead
        # near a post the hit is only trustworthy if walls run through BOTH sides of that post
        # (then the post face is flush with them); otherwise the beam may have slipped past a wall end
        local = (ax * fx + ay * fy) % CELL_SIZE_CM
        near_post = min(local, CELL_SIZE_CM - local) < WALL_THICKNESS_CM
        shifts = (-WALL_THICKNESS_CM, WALL_THICKNESS_CM) if near_post else (0.0,)
        d = RIGHT_OF[self.heading] if side > 0 else LEFT_OF[self.heading]
        for shift in shifts:
            cx, cy = int((ax + fx * shift) // CELL_SIZE_CM), int((ay + fy * shift) // CELL_SIZE_CM)
            if not (0 <= cx < COLS and 0 <= cy < ROWS):
                return False
            cell = self.memory.grid[cx][cy]
            if not (cell.walls_known[d] and cell.walls[d]):
                return False
        return True

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
        self.round_steps[self.current_round - 1] += 1

    # ------------------------------------------------------------------ motion
    def _plan_at_center(self):
        if not self.calibrated and self._front_wall_recenter():
            return
        if (self.x, self.y) in self.target_cells:
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

        if not self.decided and d_rem <= self.v ** 2 / (2 * ACCEL_CM_S2) + DECISION_MARGIN_CM:
            self._decide_after_target()
            tx, ty = cell_center(*self.target)
            d_rem = (tx - self.px) * fx + (ty - self.py) * fy

        # brake profile: never faster than what still lets us stop at the target centre
        v_max = MAX_SPEED_CM_S if self.mode == "FAST" else SEARCH_SPEED_CM_S
        v_des = math.copysign(min(v_max, math.sqrt(2 * ACCEL_CM_S2 * abs(d_rem))), d_rem)
        self.v = _approach(self.v, v_des, ACCEL_CM_S2 * dt)
        step = self.v * dt
        if self.decided and (abs(d_rem) < 0.05 or (abs(step) >= abs(d_rem) and abs(self.v) < 5)):
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

    def _decide_after_target(self):
        """Approaching the target cell: keep going straight through it, or stop there?"""
        self.decided = True
        tx, ty = self.target
        if (tx, ty) in self.target_cells:
            return                                            # stop in the goal
        step = self._choose_step(tx, ty, self.heading)
        if step and step[0] == self.heading and self._edge_known_open(tx, ty, self.heading):
            self.target, self.decided = (step[1], step[2]), False

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

    def _flood(self, optimistic):
        """BFS distance-to-nearest-goal for every cell (None = unreachable)."""
        dist = [[None] * ROWS for _ in range(COLS)]
        q = deque()
        for gx, gy in self.target_cells:
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
                turns = 0 if d == h else (2 if d == OPPOSITE[h] else 1)
                nstate, ncost = (x + dx, y + dy, d), cost + CELL_TIME + turns * TURN_TIME
                if ncost < best.get(nstate, math.inf):
                    best[nstate], parent[nstate] = ncost, state
                    heapq.heappush(pq, (ncost, nstate))
        return {}

    def _choose_step(self, x, y, heading):
        if self.mode == "FAST" and (x, y) in self.route and not self._edge_known_open(x, y, self.route[(x, y)]):
            self.route = self._fast_route()             # the map changed under the route: re-plan
            if not self.route:
                self.mode = self.round_modes[self.current_round - 1] = "SEARCH"
        if self.mode == "FAST" and (x, y) in self.route:
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

    # ------------------------------------------------------------ round end
    def _finish_round(self, crashed=False):
        # solved_optimally stays as an *informational* flag (shown in telemetry):
        # the confirmed best route is already as short as the optimistic lower
        # bound, so later rounds cannot improve it. We no longer stop early on
        # it - every run always plays out the full 3 rounds.
        self.v = self.omega = 0.0
        if crashed:
            self.round_modes[self.current_round - 1] = "CRASH"
        confirmed = self._flood(optimistic=False)
        optimistic = self._flood(optimistic=True)
        sx, sy = self.start
        if confirmed[sx][sy] is not None and confirmed[sx][sy] == optimistic[sx][sy]:
            self.solved_optimally = True

        if self.current_round < self.max_rounds:
            self.state = "ROUND_PAUSED"
        else:
            self.state = "DONE"
