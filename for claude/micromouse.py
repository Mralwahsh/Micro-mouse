# micromouse.py
from maze import Maze

class Micromouse:
    """The physical robot. Tracks its coordinates, memory map, and search logic."""
    def __init__(self):
        self.max_rounds = 3
        self.target_cells = {(4, 4), (5, 4), (4, 5), (5, 5)}
        self.reset_all()

    def reset_all(self):
        self.memory = Maze(is_blank_memory=True)
        self.x, self.y = 0, 9
        self.path_stack = [(self.x, self.y)]
        self.round_visited = set([(self.x, self.y)])
        self.global_visited = set([(self.x, self.y)])
        self.round_steps = [0, 0, 0]
        self.current_round = 1
        self.state = "IDLE"

    def start_next_round(self):
        self.current_round += 1
        self.x, self.y = 0, 9
        self.path_stack = [(self.x, self.y)]
        self.round_visited = set([(self.x, self.y)])
        self.global_visited.add((self.x, self.y))
        self.state = "EXPLORING"

    def update_logic(self, physical_maze):
        if self.state != "EXPLORING":
            return

        if (self.x, self.y) in self.target_cells:
            if self.current_round < self.max_rounds:
                self.state = "ROUND_PAUSED"
            else:
                self.state = "DONE"
            return
            
        # Update Sensors
        self.memory.grid[self.x][self.y].discovered = True
        dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
        
        for d, (dx, dy) in dirs.items():
            wall_is_closed = physical_maze.grid[self.x][self.y].walls[d]
            self.memory.grid[self.x][self.y].walls[d] = wall_is_closed
            
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < 10 and 0 <= ny < 10:
                opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
                self.memory.grid[nx][ny].walls[opp_d] = wall_is_closed
        
        # Find valid neighbors
        valid_neighbors = []
        for d, (dx, dy) in dirs.items():
            if not self.memory.grid[self.x][self.y].walls[d]:
                nx, ny = self.x + dx, self.y + dy
                if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in self.round_visited:
                    valid_neighbors.append((nx, ny))
        
        # Decision Making
        if valid_neighbors:
            jump_to_goal = None
            for nx, ny in valid_neighbors:
                if (nx, ny) in self.target_cells:
                    jump_to_goal = (nx, ny)
                    break
            
            if jump_to_goal:
                next_step = jump_to_goal
            else:
                valid_neighbors.sort(key=lambda pos: 1 if pos in self.global_visited else 0)
                next_step = valid_neighbors[0]
            
            self.x, self.y = next_step
            self.round_visited.add((self.x, self.y))
            self.global_visited.add((self.x, self.y))
            self.path_stack.append((self.x, self.y))
            
            self.round_steps[self.current_round - 1] += 1
        else:
            if len(self.path_stack) > 1:
                self.path_stack.pop()
                self.x, self.y = self.path_stack[-1]
                self.round_steps[self.current_round - 1] += 1
            else:
                self.state = "ROUND_PAUSED" if self.current_round < self.max_rounds else "DONE"