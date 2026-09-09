# maze.py
import random
from collections import deque
from cell import Cell
from config import *

class Maze:
    """Handles grid structure, generation, and shortest-path math."""
    def __init__(self, is_blank_memory=False):
        self.grid = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
        self.target_cells = {(4, 4), (5, 4), (4, 5), (5, 5)}
        
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
            directions = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
            for d, (dx, dy) in directions.items():
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS and not self.grid[nx][ny].visited:
                    walls_list.append((x, y, nx, ny, d))

        add_walls(start_x, start_y)
        
        while walls_list:
            idx = random.randint(0, len(walls_list) - 1)
            x, y, nx, ny, d = walls_list.pop(idx)
            
            if not self.grid[nx][ny].visited:
                self.grid[x][y].walls[d] = False
                opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
                self.grid[nx][ny].walls[opp_d] = False
                self.grid[nx][ny].visited = True
                add_walls(nx, ny)

        for _ in range(15):
            x = random.randint(0, COLS - 1)
            y = random.randint(0, ROWS - 1)
            if (x, y) in self.target_cells: continue
            
            d = random.choice(['N', 'S', 'E', 'W'])
            dx, dy = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}[d]
            nx, ny = x + dx, y + dy
            
            if 0 <= nx < COLS and 0 <= ny < ROWS:
                if (nx, ny) in self.target_cells: continue
                self.grid[x][y].walls[d] = False
                opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
                self.grid[nx][ny].walls[opp_d] = False

    def get_shortest_path(self, start_x, start_y):
        queue = deque([[(start_x, start_y)]])
        visited = set([(start_x, start_y)])
        dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
        
        while queue:
            path = queue.popleft()
            x, y = path[-1]
            
            if (x, y) in self.target_cells:
                return path
                
            for d, (dx, dy) in dirs.items():
                if not self.grid[x][y].walls[d]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append(path + [(nx, ny)])
        return []