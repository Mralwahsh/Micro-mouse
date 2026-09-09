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
# 4. PYGAME RENDERING
# ==========================================
def main():
    pygame.init()

    # Scaled down to 40px so three mazes fit on a standard 1080p screen
    CELL_SIZE = 40 
    WALL_THICKNESS = 4 
    COLS, ROWS = 10, 10
    
    MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + ((COLS + 1) * WALL_THICKNESS)
    MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + ((ROWS + 1) * WALL_THICKNESS)
    
    # Calculate width for 3 mazes side-by-side with 40px padding between them
    WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 3) + 160 
    WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + 140

    # Colors
    COLOR_WALL = (200, 30, 30) 
    COLOR_FLOOR = (0, 0, 0)    
    COLOR_UI_BG = (40, 40, 40)
    COLOR_FOG = (20, 20, 20)
    COLOR_START = (30, 150, 30)
    
    COLOR_PHYSICAL_MOUSE = (0, 150, 255) 
    COLOR_MEMORY_MOUSE = (0, 255, 0)     
    COLOR_VISITED_TRAIL = (70, 0, 130)   
    COLOR_SOLUTION = (255, 0, 0)         
    
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE 3-Panel Micromouse Simulator")
    font_bold = pygame.font.SysFont("Arial", 20, bold=True)
    font_small = pygame.font.SysFont("Arial", 16)
    
    current_maze = generate_ieee_maze()
    mouse_memory = [[Cell(x, y) for y in range(ROWS)] for x in range(COLS)]
    
    explore_state = "IDLE"
    solution_path = []
    target_cells = {(4, 4), (5, 4), (4, 5), (5, 5)}
    
    mouse_x, mouse_y = 0, 9 
    path_stack = [] 
    visited = set()
    
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - 70, 140, 40)
    explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - 70, 140, 40)

    clock = pygame.time.Clock()

    def draw_maze(offset_x, offset_y, title_text, maze_data, is_memory=False, show_trail=True):
        title_surf = font_bold.render(title_text, True, (255, 255, 255))
        screen.blit(title_surf, (offset_x, offset_y - 35))
        
        if not is_memory:
            # --- PHYSICAL MAZE DRAWING ---
            pygame.draw.rect(screen, COLOR_FOG, (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            start_px = offset_x + WALL_THICKNESS + (0 * (CELL_SIZE + WALL_THICKNESS))
            start_py = offset_y + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
            pygame.draw.rect(screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

            for i in range(COLS + 1):
                for j in range(ROWS + 1):
                    if i == 5 and j == 5: continue
                    px = offset_x + i * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + j * (CELL_SIZE + WALL_THICKNESS)
                    pygame.draw.rect(screen, COLOR_WALL, (px, py, WALL_THICKNESS, WALL_THICKNESS))

            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_data[x][y]
                    px = offset_x + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    pygame.draw.rect(screen, COLOR_FLOOR, (px + WALL_THICKNESS, py + WALL_THICKNESS, CELL_SIZE, CELL_SIZE))
                    if cell.walls['N']: pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['S']: pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py + CELL_SIZE + WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['W']: pygame.draw.rect(screen, COLOR_WALL, (px, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
                    if cell.walls['E']: pygame.draw.rect(screen, COLOR_WALL, (px + CELL_SIZE + WALL_THICKNESS, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
        
        else:
            # --- MEMORY MAP DRAWING ---
            pygame.draw.rect(screen, (0, 0, 0), (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            
            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_data[x][y]
                    px = offset_x + WALL_THICKNESS + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + WALL_THICKNESS + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    if cell.discovered:
                        # Draw purple trail only if requested (hides it on the 3rd maze)
                        if show_trail and (x, y) in visited:
                            pygame.draw.rect(screen, COLOR_VISITED_TRAIL, (px, py, CELL_SIZE, CELL_SIZE))
                        
                        # Draw thin white walls
                        if cell.walls['N']: pygame.draw.line(screen, (255,255,255), (px, py), (px+CELL_SIZE, py), 2)
                        if cell.walls['S']: pygame.draw.line(screen, (255,255,255), (px, py+CELL_SIZE), (px+CELL_SIZE, py+CELL_SIZE), 2)
                        if cell.walls['W']: pygame.draw.line(screen, (255,255,255), (px, py), (px, py+CELL_SIZE), 2)
                        if cell.walls['E']: pygame.draw.line(screen, (255,255,255), (px+CELL_SIZE, py), (px+CELL_SIZE, py+CELL_SIZE), 2)

    running = True
    while running:
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
                mouse_memory[mouse_x][mouse_y].discovered = True
                dirs = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
                
                for d, (dx, dy) in dirs.items():
                    wall_is_closed = current_maze[mouse_x][mouse_y].walls[d]
                    mouse_memory[mouse_x][mouse_y].walls[d] = wall_is_closed
                    
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= nx < 10 and 0 <= ny < 10:
                        opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
                        mouse_memory[nx][ny].walls[opp_d] = wall_is_closed
                
                unvisited_neighbors = []
                for d, (dx, dy) in dirs.items():
                    if not mouse_memory[mouse_x][mouse_y].walls[d]:
                        nx, ny = mouse_x + dx, mouse_y + dy
                        if 0 <= nx < 10 and 0 <= ny < 10 and (nx, ny) not in visited:
                            unvisited_neighbors.append((nx, ny))
                
                if unvisited_neighbors:
                    next_step = unvisited_neighbors[0]
                    for nx, ny in unvisited_neighbors:
                        if (nx, ny) in target_cells:
                            next_step = (nx, ny)
                            break
                    
                    mouse_x, mouse_y = next_step
                    visited.add((mouse_x, mouse_y))
                    path_stack.append((mouse_x, mouse_y))
                else:
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

        # 1. Left: Physical Maze
        offset_1 = 40
        draw_maze(offset_1, 50, "Physical Maze", current_maze, is_memory=False)
        
        # 2. Center: Memory Map (With purple search trail)
        offset_2 = MAZE_PIXEL_WIDTH + 80
        draw_maze(offset_2, 50, "Memory Map (Search Phase)", mouse_memory, is_memory=True, show_trail=True)

        # 3. Right: Fast Run Map (Clean map, no trail, just the solution)
        offset_3 = (MAZE_PIXEL_WIDTH * 2) + 120
        draw_maze(offset_3, 50, "Fast Run (Shortest Path)", mouse_memory, is_memory=True, show_trail=False)

        # Draw Solution Path ONLY on the 3rd Maze (Fast Run)
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                start_px = offset_3 + WALL_THICKNESS + (x1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                start_py = 50 + WALL_THICKNESS + (y1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_px = offset_3 + WALL_THICKNESS + (x2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_py = 50 + WALL_THICKNESS + (y2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                
                pygame.draw.line(screen, COLOR_SOLUTION, (start_px, start_py), (end_px, end_py), 4)

        # Draw the physical Mouse token (Blue Square on Left)
        if explore_state in ["EXPLORING", "PAUSED"]:
            mouse_px = offset_1 + WALL_THICKNESS + (mouse_x * (CELL_SIZE + WALL_THICKNESS)) + 2
            mouse_py = 50 + WALL_THICKNESS + (mouse_y * (CELL_SIZE + WALL_THICKNESS)) + 2
            pygame.draw.rect(screen, COLOR_PHYSICAL_MOUSE, (mouse_px, mouse_py, CELL_SIZE - 4, CELL_SIZE - 4), border_radius=4)

        # Draw the Memory Mouse token (Green Circle on Center)
        if explore_state in ["EXPLORING", "PAUSED"]:
            center_x = offset_2 + WALL_THICKNESS + (mouse_x * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
            center_y = 50 + WALL_THICKNESS + (mouse_y * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
            pygame.draw.circle(screen, COLOR_MEMORY_MOUSE, (center_x, center_y), CELL_SIZE // 3)

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

        # Fixed Dimension Text
        dim_string = "Physical Dimensions: 190.8cm x 190.8cm"
        dim_surf = font_small.render(dim_string, True, (180, 180, 180))
        dim_rect = dim_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 20))
        screen.blit(dim_surf, dim_rect)

        pygame.display.flip()
        clock.tick(20) 

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()