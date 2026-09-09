import random
import pygame
import sys
from collections import deque

# ==========================================
# 1. NODE-BASED CELL STRUCTURE
# ==========================================
class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.walls = {'N': True, 'S': True, 'E': True, 'W': True}
        self.visited = False
        self.discovered = False # Tracks if the mouse has mapped this cell

# ==========================================
# 2. IEEE MAZE GENERATOR
# ==========================================
def generate_ieee_maze():
    cols, rows = 10, 10
    grid = [[Cell(x, y) for y in range(rows)] for x in range(cols)]
    
    # The 2x2 Center Island 
    center_cells = [(4, 4), (5, 4), (4, 5), (5, 5)]
    
    # Hollow out the center room
    grid[4][4].walls['E'] = False; grid[5][4].walls['W'] = False
    grid[4][4].walls['S'] = False; grid[4][5].walls['N'] = False
    grid[5][4].walls['S'] = False; grid[5][5].walls['N'] = False
    grid[4][5].walls['E'] = False; grid[5][5].walls['W'] = False
    
    for cx, cy in center_cells:
        grid[cx][cy].visited = True 

    # Pick exactly one entrance
    entrances = [
        ((4,4), 'N', (4,3), 'S'), ((5,4), 'N', (5,3), 'S'),
        ((4,5), 'S', (4,6), 'N'), ((5,5), 'S', (5,6), 'N'),
        ((4,4), 'W', (3,4), 'E'), ((4,5), 'W', (3,5), 'E'),
        ((5,4), 'E', (6,4), 'W'), ((5,5), 'E', (6,5), 'W')
    ]
    inside, dir_out, outside, dir_in = random.choice(entrances)
    grid[inside[0]][inside[1]].walls[dir_out] = False
    grid[outside[0]][outside[1]].walls[dir_in] = False
    
    # Generate Maze starting from the Entrance
    start_x, start_y = outside
    grid[start_x][start_y].visited = True
    
    walls_list = []
    def add_walls(x, y):
        directions = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
        for d, (dx, dy) in directions.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and not grid[nx][ny].visited:
                walls_list.append((x, y, nx, ny, d))

    add_walls(start_x, start_y)
    
    while walls_list:
        idx = random.randint(0, len(walls_list) - 1)
        x, y, nx, ny, d = walls_list.pop(idx)
        
        if not grid[nx][ny].visited:
            grid[x][y].walls[d] = False
            opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
            grid[nx][ny].walls[opp_d] = False
            grid[nx][ny].visited = True
            add_walls(nx, ny)

    # Add alternate routes
    for _ in range(15):
        x = random.randint(0, cols - 1)
        y = random.randint(0, rows - 1)
        if (x, y) in center_cells: continue
        
        d = random.choice(['N', 'S', 'E', 'W'])
        dx, dy = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}[d]
        nx, ny = x + dx, y + dy
        
        if 0 <= nx < cols and 0 <= ny < rows:
            if (nx, ny) in center_cells: continue
            grid[x][y].walls[d] = False
            opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
            grid[nx][ny].walls[opp_d] = False

    return grid

# ==========================================
# 3. INTERNAL MEMORY SOLVER (BFS)
# ==========================================
def get_shortest_known_path(memory, start_x, start_y, target_cells):
    queue = deque([[(start_x, start_y)]])
    visited = set([(start_x, start_y)])
    dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
    
    while queue:
        path = queue.popleft()
        x, y = path[-1]
        
        if (x, y) in target_cells:
            return path
            
        for d, (dx, dy) in dirs.items():
            # If there is no wall blocking the direction in our memory
            if not memory[x][y].walls[d]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append(path + [(nx, ny)])
    return []

# ==========================================
# 4. PYGAME RENDERING & DUAL SCREEN STATE
# ==========================================
def main():
    pygame.init()

    # Visual Scale
    CELL_SIZE = 60 
    WALL_THICKNESS = 4 
    COLS, ROWS = 10, 10
    
    MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + ((COLS + 1) * WALL_THICKNESS)
    MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + ((ROWS + 1) * WALL_THICKNESS)
    
    # Dual screen requires doubling the width and adding margins
    WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 2) + 120 
    WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + 140

    COLOR_WALL = (200, 30, 30) 
    COLOR_FLOOR = (0, 0, 0)    
    COLOR_UI_BG = (40, 40, 40)
    COLOR_FOG = (20, 20, 20)
    COLOR_START = (30, 150, 30)
    COLOR_MOUSE = (0, 150, 255)
    COLOR_SOLUTION = (220, 50, 50)
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Real-Time Micromouse Simulator")
    font_bold = pygame.font.SysFont("Arial", 20, bold=True)
    font_small = pygame.font.SysFont("Arial", 16)
    
    # Simulation State
    current_maze = generate_ieee_maze()
    # Initialize blank memory (all walls solid, completely undiscovered)
    mouse_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
    
    explore_state = "IDLE"
    solution_path = []
    target_cells = {(4, 4), (5, 4), (4, 5), (5, 5)}
    
    # Mouse physical tracking
    # Start at bottom-left corner of the grid
    mouse_x, mouse_y = 0, 9 
    path_stack = [] 
    visited = set()
    
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - 70, 140, 40)
    explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - 70, 140, 40)

    clock = pygame.time.Clock()

    # --- HELPER FUNCTION: DRAW A MAZE ---
    def draw_maze(offset_x, offset_y, title_text, maze_data, is_memory=False):
        title_surf = font_bold.render(title_text, True, (255, 255, 255))
        screen.blit(title_surf, (offset_x, offset_y - 35))
        
        # Base background
        pygame.draw.rect(screen, COLOR_FOG, (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
        
        # Draw Start Area
        start_px = offset_x + WALL_THICKNESS + (0 * (CELL_SIZE + WALL_THICKNESS))
        start_py = offset_y + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
        pygame.draw.rect(screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

        # Lattice Posts
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if i == 5 and j == 5: continue
                px = offset_x + i * (CELL_SIZE + WALL_THICKNESS)
                py = offset_y + j * (CELL_SIZE + WALL_THICKNESS)
                pygame.draw.rect(screen, COLOR_WALL, (px, py, WALL_THICKNESS, WALL_THICKNESS))

        # Draw Cells & Walls
        for x in range(COLS):
            for y in range(ROWS):
                cell = maze_data[x][y]
                px = offset_x + x * (CELL_SIZE + WALL_THICKNESS)
                py = offset_y + y * (CELL_SIZE + WALL_THICKNESS)
                
                if is_memory and not cell.discovered:
                    # Hide the internal cell architecture if unexplored
                    pygame.draw.rect(screen, COLOR_FOG, (px + WALL_THICKNESS, py, CELL_SIZE, CELL_SIZE + WALL_THICKNESS))
                    pygame.draw.rect(screen, COLOR_FOG, (px, py + WALL_THICKNESS, CELL_SIZE + WALL_THICKNESS, CELL_SIZE))
                else:
                    pygame.draw.rect(screen, COLOR_FLOOR, (px + WALL_THICKNESS, py + WALL_THICKNESS, CELL_SIZE, CELL_SIZE))
                    if cell.walls['N']: pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['S']: pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py + CELL_SIZE + WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['W']: pygame.draw.rect(screen, COLOR_WALL, (px, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
                    if cell.walls['E']: pygame.draw.rect(screen, COLOR_WALL, (px + CELL_SIZE + WALL_THICKNESS, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))

    running = True
    while running:
        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if regen_btn.collidepoint(event.pos):
                    current_maze = generate_ieee_maze()
                    mouse_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
                    explore_state = "IDLE"
                    solution_path = []
                    path_stack.clear()
                    visited.clear()
                    
                elif explore_btn.collidepoint(event.pos):
                    if explore_state == "IDLE":
                        explore_state = "EXPLORING"
                        mouse_x, mouse_y = 0, 9
                        path_stack = [(mouse_x, mouse_y)]
                        visited = set([(mouse_x, mouse_y)])
                    elif explore_state == "PAUSED":
                        explore_state = "EXPLORING"
                        if len(path_stack) > 1:
                            path_stack.pop()
                            mouse_x, mouse_y = path_stack[-1]

        # --- EXPLORATION LOGIC ---
        if explore_state == "EXPLORING":
            if (mouse_x, mouse_y) in target_cells:
                explore_state = "PAUSED"
            else:
                # 1. Update Sensors (Reveal the current cell based on ground truth)
                mouse_memory[mouse_x][mouse_y].discovered = True
                mouse_memory[mouse_x][mouse_y].walls = dict(current_maze[mouse_x][mouse_y].walls)
                
                # 2. Look for open, UNVISITED neighbors
                unvisited_neighbors = []
                dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
                for d, (dx, dy) in dirs.items():
                    if not mouse_memory[mouse_x][mouse_y].walls[d]:
                        nx, ny = mouse_x + dx, mouse_y + dy
                        if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in visited:
                            unvisited_neighbors.append((nx, ny))
                
                if unvisited_neighbors:
                    # Move forward
                    next_x, next_y = unvisited_neighbors[0]
                    mouse_x, mouse_y = next_x, next_y
                    visited.add((mouse_x, mouse_y))
                    path_stack.append((mouse_x, mouse_y))
                else:
                    # Dead end, backtrack
                    if len(path_stack) > 1:
                        path_stack.pop()
                        mouse_x, mouse_y = path_stack[-1]
                    else:
                        explore_state = "DONE"

        # Calculate BFS shortest path on memory map
        if explore_state in ["EXPLORING", "PAUSED", "DONE"]:
            solution_path = get_shortest_known_path(mouse_memory, 0, 9, target_cells)

        # --- RENDERING ---
        screen.fill(COLOR_UI_BG)

        # Draw Left Maze (Ground Truth)
        draw_maze(40, 50, "Physical Maze (Ground Truth)", current_maze, is_memory=False)
        
        # Draw Right Maze (Memory)
        right_offset = MAZE_PIXEL_WIDTH + 80
        draw_maze(right_offset, 50, "Mouse's Memory Map", mouse_memory, is_memory=True)

        # Draw Solution Path (on the right grid)
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                # Calculate absolute center pixels for lines
                start_px = right_offset + WALL_THICKNESS + (x1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                start_py = 50 + WALL_THICKNESS + (y1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_px = right_offset + WALL_THICKNESS + (x2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_py = 50 + WALL_THICKNESS + (y2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                
                pygame.draw.line(screen, COLOR_SOLUTION, (start_px, start_py), (end_px, end_py), 4)

        # Draw the physical Mouse token
        if explore_state in ["EXPLORING", "PAUSED"]:
            mouse_px = right_offset + WALL_THICKNESS + (mouse_x * (CELL_SIZE + WALL_THICKNESS)) + 4
            mouse_py = 50 + WALL_THICKNESS + (mouse_y * (CELL_SIZE + WALL_THICKNESS)) + 4
            pygame.draw.rect(screen, COLOR_MOUSE, (mouse_px, mouse_py, CELL_SIZE - 8, CELL_SIZE - 8), border_radius=4)

        # Draw Buttons
        mouse_pos = pygame.mouse.get_pos()
        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, regen_btn, border_radius=5)
        text_surf = font_bold.render("Regenerate", True, (255, 255, 255))
        screen.blit(text_surf, text_surf.get_rect(center=regen_btn.center))

        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if explore_btn.collidepoint(mouse_pos) else COLOR_BUTTON, explore_btn, border_radius=5)
        
        btn_text = "Start Mapping"
        if explore_state == "EXPLORING": btn_text = "Mapping..."
        elif explore_state == "PAUSED": btn_text = "Explore More"
        elif explore_state == "DONE": btn_text = "Map Complete"
            
        text_surf = font_bold.render(btn_text, True, (255, 255, 255))
        screen.blit(text_surf, text_surf.get_rect(center=explore_btn.center))

        # Hardcoded Fixed Dimension Text
        dim_string = "Physical Dimensions: 190.8cm x 190.8cm"
        dim_surf = font_small.render(dim_string, True, (180, 180, 180))
        dim_rect = dim_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 20))
        screen.blit(dim_surf, dim_rect)

        pygame.display.flip()
        clock.tick(30) # Adjust FPS to make the mouse search faster/slower

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()