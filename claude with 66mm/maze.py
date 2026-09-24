# maze.py
import random
import heapq
from collections import deque
from cell import Cell
from config import *

# The start cell's only opening: towards "the next unit square clockwise" (MMRC26 rule 6.1.f).
# For the default bottom-left corner that is North.
START_OPENING = 'N'
CLOCKWISE = ['N', 'E', 'S', 'W']


class Maze:
    """Handles grid structure, generation, and shortest-path math.

    Wall keys (shared with mapper.py): ('H', x, j) is the wall on horizontal grid line j
    between posts (x, j) and (x+1, j); ('V', i, y) is the wall on vertical grid line i
    between posts (i, y) and (i, y+1). Posts are (i, j) with 0 <= i <= COLS, 0 <= j <= ROWS.
    """
    def __init__(self, is_blank_memory=False):
        self.grid = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
        self.target_cells = set(TARGET_CELLS)
        self.goal_entrance = None
        # which corner the start is in this time (rule 5.c: any of the four)
        corner = random.choice(START_CORNERS) if RANDOM_START_CORNER and not is_blank_memory \
            else (START_CELL, START_OPENING)
        self.start, self.start_opening = corner

        gxs, gys = [x for x, _ in TARGET_CELLS], [y for _, y in TARGET_CELLS]
        x0, x1, y0, y1 = min(gxs), max(gxs) + 1, min(gys), max(gys) + 1
        self.goal_posts = {(i, j) for i in range(x0, x1 + 1) for j in range(y0, y1 + 1)}
        self.goal_inner_posts = {(i, j) for i in range(x0 + 1, x1) for j in range(y0 + 1, y1)}
        self.goal_boundary = ([('H', x, y0) for x in range(x0, x1)] + [('H', x, y1) for x in range(x0, x1)] +
                              [('V', x0, y) for y in range(y0, y1)] + [('V', x1, y) for y in range(y0, y1)])
        self.goal_interior = [k for k in self.all_walls()
                              if set(self.wall_posts(k)) <= self.goal_posts and k not in self.goal_boundary]

        if not is_blank_memory:
            self._generate_ieee_maze()

    # ------------------------------------------------------------ wall helpers
    @staticmethod
    def all_walls():
        return ([('H', x, j) for x in range(COLS) for j in range(ROWS + 1)] +
                [('V', i, y) for i in range(COLS + 1) for y in range(ROWS)])

    @staticmethod
    def edge_key(x, y, d):
        """Cell edge (x, y, d) -> wall key."""
        return {'N': ('H', x, y), 'S': ('H', x, y + 1), 'W': ('V', x, y), 'E': ('V', x + 1, y)}[d]

    @staticmethod
    def wall_posts(key):
        kind, a, b = key
        return [(a, b), (a + 1, b)] if kind == 'H' else [(a, b), (a, b + 1)]

    @staticmethod
    def post_walls(i, j):
        """Keys of the walls that end at post (i, j)."""
        keys = []
        if i > 0: keys.append(('H', i - 1, j))
        if i < COLS: keys.append(('H', i, j))
        if j > 0: keys.append(('V', i, j - 1))
        if j < ROWS: keys.append(('V', i, j))
        return keys

    @staticmethod
    def is_border(key):
        kind, a, b = key
        return b in (0, ROWS) if kind == 'H' else a in (0, COLS)

    def wall(self, key):
        kind, a, b = key
        if kind == 'H':
            return self.grid[a][b].walls['N'] if b < ROWS else self.grid[a][ROWS - 1].walls['S']
        return self.grid[a][b].walls['W'] if a < COLS else self.grid[COLS - 1][b].walls['E']

    def set_wall(self, key, closed):
        kind, a, b = key
        if kind == 'H':
            if b < ROWS: self.grid[a][b].walls['N'] = closed
            if b > 0: self.grid[a][b - 1].walls['S'] = closed
        else:
            if a < COLS: self.grid[a][b].walls['W'] = closed
            if a > 0: self.grid[a - 1][b].walls['E'] = closed

    def _walls_at(self, post):
        return sum(self.wall(k) for k in self.post_walls(*post))

    # ------------------------------------------------------------- generation
    def _generate_ieee_maze(self):
        """Random maze that follows the MMRC26 maze rules:
          * 10 x 10 cells with an outer wall all round (5.a);
          * start cell in a corner, walled on three sides, open towards the next cell clockwise (5.c);
          * 2 x 2 goal in the centre with exactly one entrance, built as an ISLAND - its walls
            touch no other wall, so a wall-hugging mouse can never reach it (2.2.g, 5.e);
          * at least one wall attached to every post (5.d);
          * more than one route to the goal (5.e).
        Carve a perfect maze, apply the rules, then check every rule; retry until one passes.
        """
        for _ in range(1000):
            self._carve()
            if self._apply_rules() and not self.rule_violations():
                for col in self.grid:
                    for cell in col:
                        cell.visited = False
                return
        raise RuntimeError("could not generate a rule-compliant maze")

    def _carve(self):
        """Randomized Prim's: a perfect maze around a 2 x 2 goal room with one random entrance."""
        for col in self.grid:
            for cell in col:
                cell.walls = {d: True for d in DIRECTIONS}
                cell.visited = False
        for key in self.goal_interior:
            self.set_wall(key, False)
        for cx, cy in self.target_cells:
            self.grid[cx][cy].visited = True

        self.goal_entrance = random.choice(self.goal_boundary)
        self.set_wall(self.goal_entrance, False)
        kind, a, b = self.goal_entrance
        sides = [(a, b - 1), (a, b)] if kind == 'H' else [(a - 1, b), (a, b)]
        start_x, start_y = next(c for c in sides if c not in self.target_cells)
        self.grid[start_x][start_y].visited = True
        walls_list = []

        def add_walls(x, y):
            for d, (dx, dy) in DIRECTIONS.items():
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS and not self.grid[nx][ny].visited:
                    walls_list.append((x, y, nx, ny, d))

        add_walls(start_x, start_y)
        while walls_list:
            x, y, nx, ny, d = walls_list.pop(random.randrange(len(walls_list)))
            if not self.grid[nx][ny].visited:
                self.grid[x][y].walls[d] = False
                self.grid[nx][ny].walls[OPPOSITE[d]] = False
                self.grid[nx][ny].visited = True
                add_walls(nx, ny)

    def _apply_rules(self):
        """Turn the perfect maze into a rule-compliant one. False = give up on this one."""
        sx, sy = self.start
        start_walls = {self.edge_key(sx, sy, d) for d in DIRECTIONS}
        for d in DIRECTIONS:                                   # start: walled on three sides
            self.set_wall(self.edge_key(sx, sy, d), d != self.start_opening)

        # island goal: remove every wall that sticks out of the goal room
        keep = set(self.goal_boundary) | set(self.goal_interior)
        for post in self.goal_posts - self.goal_inner_posts:
            for key in self.post_walls(*post):
                if key not in keep:
                    self.set_wall(key, False)

        # rule 5.d: give every bare post a wall back (never one touching the goal island)
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if (i, j) in self.goal_inner_posts or self._walls_at((i, j)):
                    continue
                options = [k for k in self.post_walls(i, j)
                           if not set(self.wall_posts(k)) & self.goal_posts and k not in start_walls]
                random.shuffle(options)
                for key in options:
                    self.set_wall(key, True)
                    if self._all_reachable():
                        break
                    self.set_wall(key, False)
                else:
                    return False

        # rule 5.e: knock out a few more walls so there are several routes (loops)
        candidates = [k for k in self.all_walls()
                      if self.wall(k) and not self.is_border(k) and k not in keep and k not in start_walls]
        random.shuffle(candidates)
        opened = 0
        for key in candidates:
            if opened >= MAZE_EXTRA_OPENINGS:
                break
            if all(self._walls_at(p) > 1 for p in self.wall_posts(key)):
                self.set_wall(key, False)
                opened += 1
        return True

    # ------------------------------------------------------------ rule checks
    def _all_reachable(self):
        seen, q = {self.start}, deque([self.start])
        while q:
            x, y = q.popleft()
            for d, (dx, dy) in DIRECTIONS.items():
                n = (x + dx, y + dy)
                if not self.grid[x][y].walls[d] and n not in seen and 0 <= n[0] < COLS and 0 <= n[1] < ROWS:
                    seen.add(n)
                    q.append(n)
        return len(seen) == COLS * ROWS

    def _wall_follower_reaches_goal(self, hand):
        """Simulate a right-hand (+1) or left-hand (-1) wall follower from the start."""
        (x, y), d = self.start, self.start_opening
        for _ in range(4 * 4 * COLS * ROWS):
            if (x, y) in self.target_cells:
                return True
            for turn in (hand, 0, -hand, 2):
                nd = CLOCKWISE[(CLOCKWISE.index(d) + turn) % 4]
                if not self.grid[x][y].walls[nd]:
                    d = nd
                    x, y = x + DIRECTIONS[d][0], y + DIRECTIONS[d][1]
                    break
        return False

    def rule_violations(self):
        """Every MMRC26 maze rule this maze breaks (empty list = compliant)."""
        problems = []
        if not all(self.wall(k) for k in self.all_walls() if self.is_border(k)):
            problems.append("outer wall is not closed (5.a)")
        sx, sy = self.start
        if [d for d in DIRECTIONS if not self.grid[sx][sy].walls[d]] != [self.start_opening]:
            problems.append("start cell must be walled on three sides, open clockwise (5.c)")
        if [k for k in self.goal_boundary if not self.wall(k)] != [self.goal_entrance] or \
                any(self.wall(k) for k in self.goal_interior):
            problems.append("goal must be an open 2x2 room with exactly one entrance (5.c)")
        bare = [(i, j) for i in range(COLS + 1) for j in range(ROWS + 1)
                if (i, j) not in self.goal_inner_posts and not self._walls_at((i, j))]
        if bare:
            problems.append(f"posts without a wall: {bare} (5.d)")
        # island: walk the wall network from the goal; it must never reach the outer wall
        seen, q = set(), deque(self.goal_posts - self.goal_inner_posts)
        while q:
            p = q.popleft()
            if p in seen:
                continue
            seen.add(p)
            for key in self.post_walls(*p):
                if self.wall(key):
                    q.extend(n for n in self.wall_posts(key) if n not in seen)
        if any(i in (0, COLS) or j in (0, ROWS) for i, j in seen):
            problems.append("goal walls are connected to the outer wall - not an island (2.2.g)")
        if not self._all_reachable():
            problems.append("some cells cannot be reached")
        if sum(not self.wall(k) for k in self.all_walls()) <= COLS * ROWS - 1:
            problems.append("only one route: no loops (5.e)")
        for hand, name in ((1, "right"), (-1, "left")):
            if self._wall_follower_reaches_goal(hand):
                problems.append(f"a {name}-hand wall follower reaches the goal (5.e)")
        return problems

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
