# micromouse.py
import math
from collections import deque
from maze import Maze
from mapper import Mapper
from sensors import SensorArray
from config import (COLS, ROWS, DIRECTIONS, OPPOSITE, TARGET_CELLS, START_CELL, CELL_SIZE_CM,
                    SENSOR_HZ, MAX_SPEED_CM_S, ACCEL_CM_S2, MAX_TURN_DEG_S, TURN_ACCEL_DEG_S2)

# Heading angle of each compass direction (world y axis points down, so North = -90 deg)
HEADING_ANGLE = {'E': 0.0, 'S': math.pi / 2, 'W': math.pi, 'N': -math.pi / 2}
MAX_TURN = math.radians(MAX_TURN_DEG_S)
TURN_ACCEL = math.radians(TURN_ACCEL_DEG_S2)
DECISION_MARGIN_CM = 1.0        # decide the next move this far before the braking point


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

    Rounds: the mouse always runs the full 3 rounds. Between rounds it is
    carried back to the start by hand; the map carries over. `solved_optimally`
    is reported once the confirmed best route matches the optimistic lower
    bound (further rounds cannot improve it).
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
        self.current_round = 1
        self.state = "IDLE"
        self.solved_optimally = False
        self.global_visited = set([self.start])
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
        self.readings = []
        self.memory.grid[self.x][self.y].discovered = True

    def start_next_round(self):
        self.current_round += 1
        self._place_at_start()
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
            self._turn_step(dt)
        else:
            self._drive_step(dt)
        self._track_cell()

    # ----------------------------------------------------------------- sensing
    def _sense(self, physical_maze):
        if self.sensors is None or self.sensors.maze is not physical_maze:
            self.sensors = SensorArray(physical_maze)
        self.readings = self.sensors.scan(self.px, self.py, self.theta)
        changed = False
        for r in self.readings:
            changed |= self.mapper.add_reading(r)
        if changed:
            self.flood = self._flood(optimistic=True)

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

    def _turn_step(self, dt):
        goal = HEADING_ANGLE[self.turn_to]
        err = _wrap(goal - self.theta)
        w_des = math.copysign(min(MAX_TURN, math.sqrt(2 * TURN_ACCEL * abs(err))), err)
        self.omega = _approach(self.omega, w_des, TURN_ACCEL * dt)
        self.theta += self.omega * dt
        new_err = _wrap(goal - self.theta)
        if abs(new_err) < 1e-3 or (new_err * err < 0 and abs(new_err) < 0.5):
            self.theta, self.omega = goal, 0.0
            self.heading = self.turn_to
            self.motion = "AT_CENTER"

    def _drive_step(self, dt):
        fx, fy = DIRECTIONS[self.heading]
        tx, ty = cell_center(*self.target)
        d_rem = (tx - self.px) * fx + (ty - self.py) * fy

        if not self.decided and d_rem <= self.v ** 2 / (2 * ACCEL_CM_S2) + DECISION_MARGIN_CM:
            self._decide_after_target()
            tx, ty = cell_center(*self.target)
            d_rem = (tx - self.px) * fx + (ty - self.py) * fy

        # brake profile: never faster than what still lets us stop at the target centre
        v_des = math.copysign(min(MAX_SPEED_CM_S, math.sqrt(2 * ACCEL_CM_S2 * abs(d_rem))), d_rem)
        self.v = _approach(self.v, v_des, ACCEL_CM_S2 * dt)
        step = self.v * dt
        if self.decided and (abs(d_rem) < 0.05 or (abs(step) >= abs(d_rem) and abs(self.v) < 5)):
            self.px, self.py, self.v = tx, ty, 0.0          # arrived: settle exactly on the centre
            self.motion = "AT_CENTER"
            return
        self.px += fx * step
        self.py += fy * step

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
    def _choose_step(self, x, y, heading):
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
    def _finish_round(self):
        # solved_optimally stays as an *informational* flag (shown in telemetry):
        # the confirmed best route is already as short as the optimistic lower
        # bound, so later rounds cannot improve it. We no longer stop early on
        # it - every run always plays out the full 3 rounds.
        self.v = self.omega = 0.0
        confirmed = self._flood(optimistic=False)
        optimistic = self._flood(optimistic=True)
        sx, sy = self.start
        if confirmed[sx][sy] is not None and confirmed[sx][sy] == optimistic[sx][sy]:
            self.solved_optimally = True

        if self.current_round < self.max_rounds:
            self.state = "ROUND_PAUSED"
        else:
            self.state = "DONE"
