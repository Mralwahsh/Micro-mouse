# micromouse.py
from collections import deque
from maze import Maze
from config import COLS, ROWS, DIRECTIONS, OPPOSITE, TARGET_CELLS, START_CELL


class Micromouse:
    """The physical robot. Tracks its coordinates, memory map, and search logic.

    Navigation uses classic Micromouse *flood fill* instead of a blind DFS:

      1. SENSE  - read all four walls at the current cell (perfect sensor),
                  record them in memory and mirror them onto the neighbours.
      2. FLOOD  - breadth-first fill of a distance-to-goal grid. Unsensed edges
                  are assumed open (optimism) so the mouse always has a target
                  direction and heads for the centre from step one.
      3. STEP   - move to the open neighbour with the lowest flood value.
                  Ties break on: fewest turns (a real mouse pays for turning),
                  then unexplored cells (information gain), then a stable order.

    Discovering a wall changes the flood grid on the next tick, so the mouse
    re-routes automatically - there is no explicit backtracking stack.

    Rounds: each round is a fresh run from the start. Knowledge (the memory map)
    carries over, so every round the route tightens. The search stops early once
    the best *confirmed* route is as short as the *optimistic* lower bound - at
    that point the path is provably optimal and more exploration cannot help.
    """

    def __init__(self):
        self.max_rounds = 3
        self.target_cells = set(TARGET_CELLS)
        self.start = START_CELL
        self.reset_all()

    # ------------------------------------------------------------------ setup
    def reset_all(self):
        self.memory = Maze(is_blank_memory=True)
        self.x, self.y = self.start
        self.heading = 'N'
        self.path_stack = [self.start]          # actual trajectory this round
        self.round_visited = set([self.start])
        self.global_visited = set([self.start])
        self.round_steps = [0, 0, 0]
        self.current_round = 1
        self.state = "IDLE"
        self.solved_optimally = False
        self.flood = self._flood(optimistic=True)

    def start_next_round(self):
        self.current_round += 1
        self.x, self.y = self.start
        self.heading = 'N'
        self.path_stack = [self.start]
        self.round_visited = set([self.start])
        self.global_visited.add(self.start)
        self.state = "EXPLORING"
        self.flood = self._flood(optimistic=True)

    # -------------------------------------------------------------- main tick
    def update_logic(self, physical_maze):
        if self.state != "EXPLORING":
            return

        if (self.x, self.y) in self.target_cells:
            self._finish_round()
            return

        self._sense(physical_maze)
        self.flood = self._flood(optimistic=True)

        step = self._choose_step()
        if step is None:                       # fully walled in (invalid maze)
            self._finish_round()
            return

        d, nx, ny = step
        self.heading = d
        self.x, self.y = nx, ny
        self.round_visited.add((nx, ny))
        self.global_visited.add((nx, ny))
        self.path_stack.append((nx, ny))
        self.round_steps[self.current_round - 1] += 1

    # ----------------------------------------------------------------- sensing
    def _sense(self, physical_maze):
        cell = self.memory.grid[self.x][self.y]
        cell.discovered = True
        for d, (dx, dy) in DIRECTIONS.items():
            closed = physical_maze.grid[self.x][self.y].walls[d]
            cell.walls[d] = closed
            cell.walls_known[d] = True

            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < COLS and 0 <= ny < ROWS:
                nb = self.memory.grid[nx][ny]
                nb.walls[OPPOSITE[d]] = closed
                nb.walls_known[OPPOSITE[d]] = True

    # ------------------------------------------------------------- flood fill
    def _edge_open(self, x, y, d, optimistic):
        """Can the mouse travel from (x, y) through edge d?"""
        cell = self.memory.grid[x][y]
        if optimistic:
            # open unless we have positively confirmed a wall
            return not (cell.walls_known[d] and cell.walls[d])
        # pessimistic: only edges we have confirmed to be open
        return cell.walls_known[d] and not cell.walls[d]

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
    def _choose_step(self):
        cell = self.memory.grid[self.x][self.y]
        best_key = None
        best_move = None

        for d, (dx, dy) in DIRECTIONS.items():
            if cell.walls[d]:                        # confirmed wall (cell fully sensed)
                continue
            nx, ny = self.x + dx, self.y + dy
            if not (0 <= nx < COLS and 0 <= ny < ROWS):
                continue
            fval = self.flood[nx][ny]
            if fval is None:
                continue

            if d == self.heading:
                turn_cost = 0
            elif d == OPPOSITE[self.heading]:
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
        confirmed = self._flood(optimistic=False)
        optimistic = self._flood(optimistic=True)
        sx, sy = self.start
        if confirmed[sx][sy] is not None and confirmed[sx][sy] == optimistic[sx][sy]:
            self.solved_optimally = True

        if self.current_round < self.max_rounds and not self.solved_optimally:
            self.state = "ROUND_PAUSED"
        else:
            self.state = "DONE"
