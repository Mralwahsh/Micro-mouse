# maze.py
import random
import heapq
from collections import deque
from cell import Cell
from config import *

class Maze:
    """Handles grid structure, generation, and shortest-path math."""
    def __init__(self, is_blank_memory=False):
        self.grid = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
        self.target_cells = set(TARGET_CELLS)

        if not is_blank_memory:
            self._generate_ieee_maze()

    def _generate_ieee_maze(self):
        self.grid[4][4].walls['E'] = False; self.grid[5][4].walls['W'] = False
        self.grid[4][4].walls['S'] = False; self.grid[4][5].walls['N'] = False
        self.grid[5][4].walls['S'] = False; self.grid[5][5].walls['N'] = False
        self.grid[4][5].walls['E'] = False; self.grid[5][5].walls['W'] = False

        for cx, cy in self.target_cells:
            self.grid[cx][cy].visited = True

        entrances = [
            ((4,4), 'N', (4,3), 'S'), ((5,4), 'N', (5,3), 'S'),
            ((4,5), 'S', (4,6), 'N'), ((5,5), 'S', (5,6), 'N'),
            ((4,4), 'W', (3,4), 'E'), ((4,5), 'W', (3,5), 'E'),
            ((5,4), 'E', (6,4), 'W'), ((5,5), 'E', (6,5), 'W')
        ]
        inside, dir_out, outside, dir_in = random.choice(entrances)
        self.grid[inside[0]][inside[1]].walls[dir_out] = False
        self.grid[outside[0]][outside[1]].walls[dir_in] = False

        start_x, start_y = outside
        self.grid[start_x][start_y].visited = True
        walls_list = []

        def add_walls(x, y):
            for d, (dx, dy) in DIRECTIONS.items():
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS and not self.grid[nx][ny].visited:
                    walls_list.append((x, y, nx, ny, d))

        add_walls(start_x, start_y)

        while walls_list:
            idx = random.randint(0, len(walls_list) - 1)
            x, y, nx, ny, d = walls_list.pop(idx)

            if not self.grid[nx][ny].visited:
                self.grid[x][y].walls[d] = False
                self.grid[nx][ny].walls[OPPOSITE[d]] = False
                self.grid[nx][ny].visited = True
                add_walls(nx, ny)

        for _ in range(15):
            x = random.randint(0, COLS - 1)
            y = random.randint(0, ROWS - 1)
            if (x, y) in self.target_cells: continue

            d = random.choice(list(DIRECTIONS))
            dx, dy = DIRECTIONS[d]
            nx, ny = x + dx, y + dy

            if 0 <= nx < COLS and 0 <= ny < ROWS:
                if (nx, ny) in self.target_cells: continue
                self.grid[x][y].walls[d] = False
                self.grid[nx][ny].walls[OPPOSITE[d]] = False

    def get_shortest_path(self, start_x, start_y):
        queue = deque([[(start_x, start_y)]])
        visited = set([(start_x, start_y)])

        while queue:
            path = queue.popleft()
            x, y = path[-1]

            if (x, y) in self.target_cells:
                return path

            for d, (dx, dy) in DIRECTIONS.items():
                if not self.grid[x][y].walls[d]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < COLS and 0 <= ny < ROWS and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append(path + [(nx, ny)])
        return []

    def get_least_turn_path(self, start_x, start_y, start_heading='N'):
        """Path to the goal that makes the fewest turns (ties broken by length).

        Dijkstra over (x, y, heading) states with cost = (turns, steps). A real
        mouse pays to decelerate, rotate and re-accelerate, so among all equally
        long routes the one with the longest straights is the genuinely fastest.
        """
        start = (start_x, start_y, start_heading)
        best = {start: (0, 0)}
        counter = 0
        pq = [(0, 0, counter, start_x, start_y, start_heading, [(start_x, start_y)])]

        while pq:
            turns, steps, _, x, y, heading, path = heapq.heappop(pq)
            if (x, y) in self.target_cells:
                return path
            if (turns, steps) > best.get((x, y, heading), (turns, steps)):
                continue
            for d, (dx, dy) in DIRECTIONS.items():
                if self.grid[x][y].walls[d]:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < COLS and 0 <= ny < ROWS):
                    continue
                n_turns = turns + (0 if d == heading else 1)
                n_steps = steps + 1
                nstate = (nx, ny, d)
                if (n_turns, n_steps) < best.get(nstate, (10**9, 10**9)):
                    best[nstate] = (n_turns, n_steps)
                    counter += 1
                    heapq.heappush(pq, (n_turns, n_steps, counter, nx, ny, d,
                                        path + [(nx, ny)]))
        return []

    @staticmethod
    def count_turns(path, start_heading='N'):
        """Number of direction changes along a list of (x, y) cells."""
        if not path or len(path) < 2:
            return 0
        heading, turns = start_heading, 0
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            for d, (dx, dy) in DIRECTIONS.items():
                if (x2 - x1, y2 - y1) == (dx, dy):
                    if d != heading:
                        turns += 1
                    heading = d
                    break
        return turns
