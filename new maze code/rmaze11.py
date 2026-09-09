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
        self.discovered = False

def copy_memory(source_grid, cols, rows):
    """Creates a deep snapshot of the mouse's memory at a specific point in time."""
    dest_grid = [[Cell(x, y) for y in range(rows)] for x in range(cols)]
    for x in range(cols):
        for y in range(rows):
            dest_grid[x][y].walls = dict(source_grid[x][y].walls)
            dest_grid[x][y].discovered = source_grid[x][y].discovered
    return dest_grid

# ==========================================
# 2. IEEE MAZE GENERATOR
# ==========================================
def generate_ieee_maze():
    cols, rows = 10, 10
    grid = [[Cell(x, y) for y in range(rows)] for x in range(cols)]
    
    center_cells = [(4, 4), (5, 4), (4, 5), (5, 5)]
    
    grid[4][4].walls['E'] = False; grid[5][4].walls['W'] = False
    grid[4][4].walls['S'] = False; grid[4][5].walls['N'] = False
    grid[5][4].walls['S'] = False; grid[5][5].walls['N'] = False
    grid[4][5].walls['E'] = False; grid[5][5].walls['W'] = False
    
    for cx, cy in center_cells:
        grid[cx][cy].visited = True 

    entrances = [
        ((4,4), 'N', (4,3), 'S'), ((5,4), 'N', (5,3), 'S'),
        ((4,5), 'S', (4,6), 'N'), ((5,5), 'S', (5,6), 'N'),
        ((4,4), 'W', (3,4), 'E'), ((4,5), 'W', (3,5), 'E'),
        ((5,4), 'E', (6,4), 'W'), ((5,5), 'E', (6,5), 'W')
    ]
    inside, dir_out, outside, dir_in = random.choice(entrances)
    grid[inside[0]][inside[1]].walls[dir_out] = False
    grid[outside[0]][outside[1]].walls[dir_in] = False
    
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
            if not memory[x][y].walls[d]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append(path + [(nx, ny)])
    return []

# ==========================================
# 4. PYGAME RENDERING & DASHBOARD
# ==========================================
def main():
    pygame.init()

    CELL_SIZE = 32 
    WALL_THICKNESS = 3 
    COLS, ROWS = 10, 10
    
    MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + ((COLS + 1) * WALL_THICKNESS)
    MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + ((ROWS + 1) * WALL_THICKNESS)
    
    PADDING = 30
    WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 4) + (PADDING * 5)
    WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + 160

    # Colors
    COLOR_WALL_BLUE = (30, 100, 255) # Absolute path walls
    COLOR_FLOOR = (0, 0, 0)    
    COLOR_UI_BG = (40, 40, 40)
    COLOR_FOG = (20, 20, 20)
    COLOR_START = (30, 150, 30)
    
    COLOR_MEMORY_MOUSE = (0, 255, 0)     
    COLOR_VISITED_TRAIL = (70, 0, 130)   
    COLOR_SOLUTION = (255, 0, 0)         
    
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT_METRIC = (180, 220, 255) 

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Learning Evolution Dashboard (Rounds 1-3 vs Absolute)")
    font_bold = pygame.font.SysFont("Arial", 16, bold=True)
    font_small = pygame.font.SysFont("Arial", 14)
    font_btn = pygame.font.SysFont("Arial", 18, bold=True)
    
    # Ground Truth Generation
    current_maze = generate_ieee_maze()
    target_cells = {(4, 4), (5, 4), (4, 5), (5, 5)}
    absolute_shortest_path = get_shortest_known_path(current_maze, 0, 9, target_cells)
    
    # Live Exploration Variables
    explore_state = "IDLE"
    current_round = 1
    max_rounds = 3
    mouse_x, mouse_y = 0, 9 
    path_stack = [] 
    global_visited = set()  
    
    # Round-Specific History Tracking (Snapshots)
    mouse_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
    blank_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
    history_memory = [copy_memory(blank_memory, COLS, ROWS) for _ in range(3)]
    history_trails = [set(), set(), set()]
    history_solutions = [[], [], []]
    history_steps = [0, 0, 0]
    
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - 70, 140, 40)
    explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - 70, 140, 40)

    clock = pygame.time.Clock()

    def draw_maze(offset_x, offset_y, title_text, maze_data, is_memory=True, trail_set=None, path_to_draw=None, wall_color=None):
        title_surf = font_bold.render(title_text, True, (255, 255, 255))
        screen.blit(title_surf, (offset_x, offset_y - 25))
        
        if not is_memory:
            # --- PANEL 4 (ABSOLUTE TRUTH - BLUE WALLS) ---
            pygame.draw.rect(screen, COLOR_FOG, (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            start_px = offset_x + WALL_THICKNESS + (0 * (CELL_SIZE + WALL_THICKNESS))
            start_py = offset_y + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
            pygame.draw.rect(screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

            for i in range(COLS + 1):
                for j in range(ROWS + 1):
                    if i == 5 and j == 5: continue
                    px = offset_x + i * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + j * (CELL_SIZE + WALL_THICKNESS)
                    pygame.draw.rect(screen, wall_color, (px, py, WALL_THICKNESS, WALL_THICKNESS))

            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_data[x][y]
                    px = offset_x + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    pygame.draw.rect(screen, COLOR_FLOOR, (px + WALL_THICKNESS, py + WALL_THICKNESS, CELL_SIZE, CELL_SIZE))
                    if cell.walls['N']: pygame.draw.rect(screen, wall_color, (px + WALL_THICKNESS, py, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['S']: pygame.draw.rect(screen, wall_color, (px + WALL_THICKNESS, py + CELL_SIZE + WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['W']: pygame.draw.rect(screen, wall_color, (px, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
                    if cell.walls['E']: pygame.draw.rect(screen, wall_color, (px + CELL_SIZE + WALL_THICKNESS, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
        
        else:
            # --- PANELS 1-3 (MEMORY MAPS - WHITE WALLS) ---
            pygame.draw.rect(screen, (0, 0, 0), (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            
            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_data[x][y]
                    px = offset_x + WALL_THICKNESS + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + WALL_THICKNESS + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    if cell.discovered:
                        if trail_set and (x, y) in trail_set:
                            pygame.draw.rect(screen, COLOR_VISITED_TRAIL, (px, py, CELL_SIZE, CELL_SIZE))
                        
                        if cell.walls['N']: pygame.draw.line(screen, (255,255,255), (px, py), (px+CELL_SIZE, py), 1)
                        if cell.walls['S']: pygame.draw.line(screen, (255,255,255), (px, py+CELL_SIZE), (px+CELL_SIZE, py+CELL_SIZE), 1)
                        if cell.walls['W']: pygame.draw.line(screen, (255,255,255), (px, py), (px, py+CELL_SIZE), 1)
                        if cell.walls['E']: pygame.draw.line(screen, (255,255,255), (px+CELL_SIZE, py), (px+CELL_SIZE, py+CELL_SIZE), 1)

        # Draw requested solution path (Red line)
        if path_to_draw:
            for i in range(len(path_to_draw) - 1):
                x1, y1 = path_to_draw[i]
                x2, y2 = path_to_draw[i+1]
                start_px = offset_x + WALL_THICKNESS + (x1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                start_py = offset_y + WALL_THICKNESS + (y1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_px = offset_x + WALL_THICKNESS + (x2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_py = offset_y + WALL_THICKNESS + (y2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                
                pygame.draw.line(screen, COLOR_SOLUTION, (start_px, start_py), (end_px, end_py), 3)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if regen_btn.collidepoint(event.pos):
                    # Hard Reset
                    current_maze = generate_ieee_maze()
                    absolute_shortest_path = get_shortest_known_path(current_maze, 0, 9, target_cells)
                    mouse_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
                    history_memory = [copy_memory(blank_memory, COLS, ROWS) for _ in range(3)]
                    history_trails = [set(), set(), set()]
                    history_solutions = [[], [], []]
                    history_steps = [0, 0, 0]
                    explore_state = "IDLE"
                    current_round = 1
                    path_stack.clear()
                    global_visited.clear()
                    
                elif explore_btn.collidepoint(event.pos):
                    if explore_state == "IDLE":
                        explore_state = "EXPLORING"
                        current_round = 1
                        mouse_x, mouse_y = 0, 9
                        path_stack = [(mouse_x, mouse_y)]
                        history_trails[0].add((mouse_x, mouse_y))
                        global_visited.add((mouse_x, mouse_y))
                        
                    elif explore_state == "ROUND_PAUSED":
                        current_round += 1
                        explore_state = "EXPLORING"
                        mouse_x, mouse_y = 0, 9
                        path_stack = [(mouse_x, mouse_y)]
                        history_trails[current_round - 1].add((mouse_x, mouse_y))
                        global_visited.add((mouse_x, mouse_y))

        # --- 3-ROUND EXPLORATION LOGIC ---
        if explore_state == "EXPLORING":
            r_idx = current_round - 1
            
            # Update Live Route finding
            history_solutions[r_idx] = get_shortest_known_path(mouse_memory, 0, 9, target_cells)

            if (mouse_x, mouse_y) in target_cells:
                # Reached goal! Freeze memory for this round
                history_memory[r_idx] = copy_memory(mouse_memory, COLS, ROWS)
                
                if current_round < max_rounds:
                    explore_state = "ROUND_PAUSED"
                else:
                    explore_state = "DONE"
            else:
                mouse_memory[mouse_x][mouse_y].discovered = True
                dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
                
                for d, (dx, dy) in dirs.items():
                    wall_is_closed = current_maze[mouse_x][mouse_y].walls[d]
                    mouse_memory[mouse_x][mouse_y].walls[d] = wall_is_closed
                    
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= nx < 10 and 0 <= ny < 10:
                        opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
                        mouse_memory[nx][ny].walls[opp_d] = wall_is_closed
                
                valid_neighbors = []
                for d, (dx, dy) in dirs.items():
                    if not mouse_memory[mouse_x][mouse_y].walls[d]:
                        nx, ny = mouse_x + dx, mouse_y + dy
                        if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in history_trails[r_idx]:
                            valid_neighbors.append((nx, ny))
                
                if valid_neighbors:
                    # PRIORITY 1: Always dive into the goal if it's open
                    jump_to_goal = None
                    for nx, ny in valid_neighbors:
                        if (nx, ny) in target_cells:
                            jump_to_goal = (nx, ny)
                            break
                    
                    if jump_to_goal:
                        next_step = jump_to_goal
                    else:
                        # PRIORITY 2: Force exploration of globally new paths
                        valid_neighbors.sort(key=lambda pos: 1 if pos in global_visited else 0)
                        next_step = valid_neighbors[0]
                    
                    mouse_x, mouse_y = next_step
                    history_trails[r_idx].add((mouse_x, mouse_y))
                    global_visited.add((mouse_x, mouse_y))
                    path_stack.append((mouse_x, mouse_y))
                    
                    history_steps[r_idx] += 1
                else:
                    if len(path_stack) > 1:
                        path_stack.pop()
                        mouse_x, mouse_y = path_stack[-1]
                        history_steps[r_idx] += 1
                    else:
                        # Back at start, nowhere else to go. Freeze memory.
                        history_memory[r_idx] = copy_memory(mouse_memory, COLS, ROWS)
                        explore_state = "ROUND_PAUSED" if current_round < max_rounds else "DONE"

        # --- RENDERING ---
        screen.fill(COLOR_UI_BG)

        text_y_pos = 50 + MAZE_PIXEL_HEIGHT + 15
        def draw_centered_text(text, center_x, y, color=COLOR_TEXT_METRIC):
            surf = font_small.render(text, True, color)
            rect = surf.get_rect(center=(center_x, y))
            screen.blit(surf, rect)

        # Draw Panels 1, 2, 3 (The 3 Rounds)
        for idx in range(3):
            offset = PADDING + (idx * (MAZE_PIXEL_WIDTH + PADDING))
            center = offset + (MAZE_PIXEL_WIDTH // 2)
            
            # Determine which memory grid to display
            if current_round == idx + 1 and explore_state != "IDLE":
                mem_to_draw = mouse_memory # Draw live updating memory
            else:
                mem_to_draw = history_memory[idx] # Draw frozen past memory, or blank future memory

            title = f"Round {idx + 1}"
            draw_maze(offset, 50, title, mem_to_draw, is_memory=True, trail_set=history_trails[idx], path_to_draw=history_solutions[idx])
            
            # Telemetry Text
            if history_steps[idx] > 0 or (current_round == idx + 1 and explore_state != "IDLE"):
                step_text = f"Search: {history_steps[idx]} steps | Route: {len(history_solutions[idx])} cells"
            else:
                step_text = "Waiting for round..."
            draw_centered_text(step_text, center, text_y_pos)
            
            # Draw Live Mouse Token ONLY on the active panel
            if current_round == idx + 1 and explore_state in ["EXPLORING", "ROUND_PAUSED"]:
                mouse_px = offset + WALL_THICKNESS + (mouse_x * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                mouse_py = 50 + WALL_THICKNESS + (mouse_y * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                pygame.draw.circle(screen, COLOR_MEMORY_MOUSE, (mouse_px, mouse_py), CELL_SIZE // 3)

        # Draw Panel 4 (Absolute Shortest Path)
        offset_4 = PADDING + (3 * (MAZE_PIXEL_WIDTH + PADDING))
        center_4 = offset_4 + (MAZE_PIXEL_WIDTH // 2)
        draw_maze(offset_4, 50, "Absolute Shortest Path", current_maze, is_memory=False, path_to_draw=absolute_shortest_path, wall_color=COLOR_WALL_BLUE)
        perfect_len = len(absolute_shortest_path) if absolute_shortest_path else 0
        draw_centered_text(f"Perfect Route: {perfect_len} cells", center_4, text_y_pos)


        # Draw Buttons
        mouse_pos = pygame.mouse.get_pos()
        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, regen_btn, border_radius=5)
        text_surf = font_btn.render("Regenerate", True, (255, 255, 255))
        screen.blit(text_surf, text_surf.get_rect(center=regen_btn.center))

        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if explore_btn.collidepoint(mouse_pos) else COLOR_BUTTON, explore_btn, border_radius=5)
        
        btn_text = "Start Round 1"
        if explore_state == "EXPLORING": btn_text = f"Running R{current_round}..."
        elif explore_state == "ROUND_PAUSED": btn_text = f"Start Round {current_round + 1}"
        elif explore_state == "DONE": btn_text = "Analysis Complete"
            
        text_surf = font_btn.render(btn_text, True, (255, 255, 255))
        screen.blit(text_surf, text_surf.get_rect(center=explore_btn.center))

        # Fixed Dimension Text
        dim_string = "Physical Dimensions: 190.8cm x 190.8cm"
        dim_surf = font_small.render(dim_string, True, (180, 180, 180))
        dim_rect = dim_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 20))
        screen.blit(dim_surf, dim_rect)

        pygame.display.flip()
        clock.tick(30) 

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()