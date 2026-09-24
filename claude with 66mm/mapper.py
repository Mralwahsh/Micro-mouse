# mapper.py
import math
from collections import deque
from sensors import noise_sigma
from config import (COLS, ROWS, CELL_SIZE_CM, WALL_THICKNESS_CM, DIRECTIONS, OPPOSITE,
                    WALL_EVIDENCE_THRESHOLD, OPEN_EVIDENCE_THRESHOLD, WALL_EVIDENCE_MAX, DRIVEN_VOTE)

HALF_WALL = WALL_THICKNESS_CM / 2
POST_MARGIN = HALF_WALL + 1.5      # readings this close to a post are ambiguous and ignored
HIT_TOLERANCE = HALF_WALL + 1.0    # extra free-space margin kept short of every hit
DROPOUT_GUARD_CM = 10.0            # "nothing in range" right after a hit this far inside range = dropout
MAP_RANGE_CM = 45.0                # only trust this much of a beam: the pose estimate is never perfect


class Mapper:
    """Builds the mouse's wall map from raw distance readings, like a real mouse.

    Every edge (wall slot) carries an evidence score:
      * a beam that ENDS on a wall slot votes "wall"  (+1)
      * a beam that PASSES a wall slot votes "open"   (-1)
      * driving through an edge is strong evidence it is open (-DRIVEN_VOTE)
    An edge becomes a known wall at +WALL_EVIDENCE_THRESHOLD and known open only at the
    stricter -OPEN_EVIDENCE_THRESHOLD,
    so a single noisy reading can never put a wall in (or take one out of) the map.

    Edge keys: ('H', x, j) = horizontal slot on grid line y = j above cell column x,
               ('V', i, y) = vertical slot on grid line x = i beside cell row y.
    """
    def __init__(self, memory):
        self.memory = memory
        self.score = {}
        self.hits = deque(maxlen=400)       # recent hit points, for the dashboard point cloud
        self.last_distance = {}             # per sensor, for the dropout filter
        for x in range(COLS):
            self.score[('H', x, 0)] = WALL_EVIDENCE_MAX
            self.score[('H', x, ROWS)] = WALL_EVIDENCE_MAX
        for y in range(ROWS):
            self.score[('V', 0, y)] = WALL_EVIDENCE_MAX
            self.score[('V', COLS, y)] = WALL_EVIDENCE_MAX
        for key in list(self.score):
            self._sync(key)

    # ----------------------------------------------------------- edge helpers
    @staticmethod
    def edge_key(x, y, d):
        """Cell edge (x, y, d) -> slot key."""
        if d == 'N': return ('H', x, y)
        if d == 'S': return ('H', x, y + 1)
        if d == 'W': return ('V', x, y)
        return ('V', x + 1, y)

    @staticmethod
    def _cell_edge(key):
        """Slot key -> one cell edge (x, y, d) that touches it."""
        kind, a, b = key
        if kind == 'H':
            return (a, b, 'N') if b < ROWS else (a, ROWS - 1, 'S')
        return (a, b, 'W') if a < COLS else (COLS - 1, b, 'E')

    def _sync(self, key):
        """Mirror an edge's score into the memory Maze (both cells). Returns True if it changed."""
        s = self.score.get(key, 0)
        known = s >= WALL_EVIDENCE_THRESHOLD or s <= -OPEN_EVIDENCE_THRESHOLD
        closed = s > 0 if known else True          # unknown edges stay "closed" in memory, as before
        x, y, d = self._cell_edge(key)
        cell = self.memory.grid[x][y]
        changed = cell.walls_known[d] != known or (known and cell.walls[d] != closed)
        cell.walls[d], cell.walls_known[d] = closed, known
        dx, dy = DIRECTIONS[d]
        nx, ny = x + dx, y + dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            nb = self.memory.grid[nx][ny]
            nb.walls[OPPOSITE[d]], nb.walls_known[OPPOSITE[d]] = closed, known
        return changed

    def _vote(self, key, amount):
        kind, a, b = key
        if kind == 'H' and not (0 <= a < COLS and 0 < b < ROWS): return False   # border is fixed
        if kind == 'V' and not (0 < a < COLS and 0 <= b < ROWS): return False
        s = self.score.get(key, 0) + amount
        self.score[key] = max(-WALL_EVIDENCE_MAX, min(WALL_EVIDENCE_MAX, s))
        return self._sync(key)

    def mark_wall(self, x, y, d):
        """A wall the rules guarantee (e.g. the start cell's three walls): known from the start."""
        key = self.edge_key(x, y, d)
        self.score[key] = WALL_EVIDENCE_MAX
        return self._sync(key)

    def mark_driven(self, x, y, d):
        """The mouse physically drove through this edge: it is certainly open."""
        return self._vote(self.edge_key(x, y, d), -DRIVEN_VOTE)

    # ---------------------------------------------------------- sensor input
    def add_reading(self, r):
        """Fold one Reading into the map. Returns True if any edge became known / changed."""
        ox, oy = r.origin
        dx, dy = r.direction
        rng = min(r.sensor["range"], MAP_RANGE_CM)
        name = r.sensor["name"]
        last = self.last_distance.get(name)
        self.last_distance[name] = r.distance
        if r.distance is None and last is not None and last < r.sensor["range"] - DROPOUT_GUARD_CM:
            return False    # a wall well inside range can't vanish in one sample: treat as a dropout
        if r.distance is not None and r.distance > rng:
            r = type(r)(r.sensor, r.origin, r.direction, None, r.end)   # too far to trust: free space only
        if r.distance is not None:
            sigma = noise_sigma(r.sensor, r.distance)
            free_len = r.distance - HIT_TOLERANCE - 3 * sigma
        else:
            free_len = rng - HIT_TOLERANCE
        changed = False

        # open evidence: every slot the beam crossed well before it ended
        for kind, o, d, p, pd, count in (('V', ox, dx, oy, dy, COLS), ('H', oy, dy, ox, dx, ROWS)):
            if d == 0:
                continue
            lo, hi = sorted((o, o + d * free_len))
            for line in range(math.ceil(lo / CELL_SIZE_CM), math.floor(hi / CELL_SIZE_CM) + 1):
                if not 0 <= line <= count:
                    continue
                t = (line * CELL_SIZE_CM - o) / d
                if not 0 < t < free_len:
                    continue
                along = p + pd * t                                  # position along the slot
                idx = math.floor(along / CELL_SIZE_CM)
                local = along - idx * CELL_SIZE_CM
                if POST_MARGIN < local < CELL_SIZE_CM - POST_MARGIN:
                    key = ('V', line, idx) if kind == 'V' else ('H', idx, line)
                    changed |= self._vote(key, -1)

        # wall evidence: which wall face does the beam reach at the measured distance?
        if r.distance is not None:
            hx, hy = ox + dx * r.distance, oy + dy * r.distance
            self.hits.append((hx, hy))
            tol = 0.5 + 3 * sigma                     # noise acts ALONG the beam
            fits = []     # every surface the beam could have hit at this distance: wall key, or None = post
            for kind, o, d, p, pd, h in (('V', ox, dx, oy, dy, hx), ('H', oy, dy, ox, dx, hy)):
                if d == 0:
                    continue
                line = round(h / CELL_SIZE_CM)
                face = line * CELL_SIZE_CM - math.copysign(HALF_WALL, d)   # the side facing the sensor
                t = (face - o) / d
                if abs(t - r.distance) > tol:
                    continue
                along = p + pd * t
                idx = math.floor(along / CELL_SIZE_CM)
                local = along - idx * CELL_SIZE_CM
                if POST_MARGIN < local < CELL_SIZE_CM - POST_MARGIN:
                    fits.append(('V', line, idx) if kind == 'V' else ('H', idx, line))
                else:
                    fits.append(None)
            if len(fits) == 1 and fits[0] is not None:
                changed |= self._vote(fits[0], +1)
            # a post, or more than one surface fits (corner): too ambiguous, no wall evidence
        return changed
