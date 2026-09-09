import random
import pygame
import sys
from collections import deque

# ==========================================
# 1. MAZE GENERATION
# ==========================================
def generate_maze(width, height):
    grid_w = width * 2 + 1
    grid_h = height * 2 + 1
    maze = [[1] * grid_w for _ in range(grid_h)]
    
    start_x, start_y = 0, 0
    maze[1][1] = 0 
    
    walls = [(2, 1, 1, 0), (1, 2, 0, 1)]
    visited = set([(0, 0)])
    
    while walls:
        idx = random.randint(0, len(walls) - 1)
        wx, wy, nx, ny = walls.pop(idx)
        
        if (nx, ny) not in visited:
            maze[wy][wx] = 0
            maze[ny * 2 + 1][nx * 2 + 1] = 0
            visited.add((nx, ny))
            
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nnx, nny = nx + dx, ny + dy
                if 0 <= nnx < width and 0 <= nny < height and (nnx, nny) not in visited:
                    nwx, nwy = nx * 2 + 1 + dx, ny * 2 + 1 + dy
                    walls.append((nwx, nwy, nnx, nny))
                    
    num_loops = (width * height) // 4 # Increased loops slightly for more alternate paths
    for _ in range(num_loops):
        x = random.randint(1, grid_w - 2)
        y = random.randint(1, grid_h - 2)
        
        if maze[y][x] == 1:
            if maze[y][x-1] == 0 and maze[y][x+1] == 0 and maze[y-1][x] == 1 and maze[y+1][x] == 1:
                maze[y][x] = 0
            elif maze[y-1][x] == 0 and maze[y+1][x] == 0 and maze[y][x-1] == 1 and maze[y][x+1] == 1:
                maze[y][x] = 0

    maze[1][0] = 0
    maze[grid_h - 2][grid_w - 1] = 0
    
    return maze

# ==========================================
# 2. INTERNAL MEMORY SOLVER (BFS)
# ==========================================
def get_shortest_known_path(memory, start_x, start_y, end_x, end_y):
    # Calculates the shortest path using ONLY what the mouse has discovered so far
    queue = deque([[(start_x, start_y)]])
    visited = set([(start_x, start_y)])
    
    while queue:
        path = queue.popleft()
        x, y = path[-1]
        
        if x == end_x and y == end_y:
            return path
            
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= ny < len(memory) and 0 <= nx < len(memory[0]):
                # Must be a KNOWN path (0). It will ignore unknown (2) and walls (1)
                if memory[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append(path + [(nx, ny)])
    return [] # Returns empty if the goal hasn't been connected to the start yet

# ==========================================
# 3. PYGAME RENDERING & STATE MACHINE
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 20
    MAZE_HEIGHT = 20
    CELL_SIZE = 15
    
    GRID_W = MAZE_WIDTH * 2 + 1
    GRID_H = MAZE_HEIGHT * 2 + 1
    
    MAZE_PIXEL_WIDTH = GRID_W * CELL_SIZE
    WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 2) + 40
    UI_HEIGHT = 80
    WINDOW_HEIGHT = (GRID_H * CELL_SIZE) + UI_HEIGHT

    # Colors
    COLOR_WALL = (40, 40, 40)
    COLOR_PATH = (240, 240, 240)
    COLOR_UNKNOWN = (0, 0, 0)
    COLOR_SOLUTION = (220, 50, 50)
    COLOR_MOUSE = (0, 150, 255) 
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Micromouse Simulator - Search & Optimize")
    font = pygame.font.SysFont("Arial", 18, bold=True)
    title_font = pygame.font.SysFont("Arial", 22, bold=True)

    # State variables
    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
    
    explore_state = "IDLE" # States: IDLE, EXPLORING, PAUSED, DONE
    solution_path = []
    
    # Mouse physical tracking
    mouse_x, mouse_y = 0, 1
    path_stack = [] 
    visited = set()
    
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)
    explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)

    clock = pygame.time.Clock()

    running = True
    while running:
        end_x, end_y = GRID_W - 1, GRID_H - 2

        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if regen_btn.collidepoint(event.pos):
                    # Hard Reset
                    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
                    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
                    explore_state = "IDLE"
                    solution_path = []
                    path_stack.clear()
                    visited.clear()
                    
                elif explore_btn.collidepoint(event.pos):
                    if explore_state == "IDLE":
                        # Start completely fresh run
                        explore_state = "EXPLORING"
                        mouse_x, mouse_y = 0, 1
                        path_stack = [(mouse_x, mouse_y)]
                        visited = set([(mouse_x, mouse_y)])
                        
                    elif explore_state == "PAUSED":
                        # Resume mapping: Force the mouse to step back out of the goal 
                        # so it doesn't immediately pause again on the next frame
                        explore_state = "EXPLORING"
                        if len(path_stack) > 1:
                            path_stack.pop()
                            mouse_x, mouse_y = path_stack[-1]

        # --- EXPLORATION LOGIC (Runs continuously while in EXPLORING state) ---
        if explore_state == "EXPLORING":
            if mouse_x == end_x and mouse_y == end_y:
                # Reached the goal! Pause so the user can see it, calculate path.
                explore_state = "PAUSED"
            else:
                # 1. Update Mouse Sensors
                mouse_memory[mouse_y][mouse_x] = current_maze[mouse_y][mouse_x]
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W:
                        mouse_memory[ny][nx] = current_maze[ny][nx]
                
                # 2. Look for open, UNVISITED neighbors
                unvisited_neighbors = []
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W:
                        if mouse_memory[ny][nx] == 0 and (nx, ny) not in visited:
                            unvisited_neighbors.append((nx, ny))
                
                if unvisited_neighbors:
                    # Move forward
                    next_x, next_y = unvisited_neighbors[0]
                    mouse_x, mouse_y = next_x, next_y
                    visited.add((mouse_x, mouse_y))
                    path_stack.append((mouse_x, mouse_y))
                else:
                    # Dead end, physically backtrack
                    if len(path_stack) > 1:
                        path_stack.pop() 
                        mouse_x, mouse_y = path_stack[-1] 
                    else:
                        # If stack is empty, we checked literally everything and are back at start
                        explore_state = "DONE"

        # Dynamically calculate the shortest known path every frame based on memory
        if explore_state in ["EXPLORING", "PAUSED", "DONE"]:
            solution_path = get_shortest_known_path(mouse_memory, 0, 1, end_x, end_y)

        # --- DRAWING ---
        screen.fill((200, 200, 200))

        def draw_grid(maze_data, offset_x, title):
            text_surf = title_font.render(title, True, (0,0,0))
            screen.blit(text_surf, (offset_x, 10))
            
            for y, row in enumerate(maze_data):
                for x, cell in enumerate(row):
                    rect = pygame.Rect(offset_x + (x * CELL_SIZE), 40 + (y * CELL_SIZE), CELL_SIZE, CELL_SIZE)
                    if cell == 1:
                        pygame.draw.rect(screen, COLOR_WALL, rect)
                    elif cell == 0:
                        pygame.draw.rect(screen, COLOR_PATH, rect)
                    elif cell == 2:
                        pygame.draw.rect(screen, COLOR_UNKNOWN, rect)

        draw_grid(current_maze, 10, "Physical Maze")
        right_offset = MAZE_PIXEL_WIDTH + 30
        draw_grid(mouse_memory, right_offset, "Mouse's Memory Map")

        # Draw the dynamic shortest solution path
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                start_pos = (right_offset + (x1 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y1 * CELL_SIZE) + CELL_SIZE // 2)
                end_pos = (right_offset + (x2 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y2 * CELL_SIZE) + CELL_SIZE // 2)
                pygame.draw.line(screen, COLOR_SOLUTION, start_pos, end_pos, 4)

        # Draw the physical Mouse
        if explore_state in ["EXPLORING", "PAUSED"]:
            mouse_rect = pygame.Rect(
                right_offset + (mouse_x * CELL_SIZE) + 2, 
                40 + (mouse_y * CELL_SIZE) + 2, 
                CELL_SIZE - 4, CELL_SIZE - 4
            )
            pygame.draw.rect(screen, COLOR_MOUSE, mouse_rect, border_radius=3)

        # Draw Buttons
        mouse_pos = pygame.mouse.get_pos()
        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, regen_btn, border_radius=5)
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=regen_btn.center))

        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if explore_btn.collidepoint(mouse_pos) else COLOR_BUTTON, explore_btn, border_radius=5)
        
        # Change button text based on state machine
        if explore_state == "IDLE":
            btn_text = "Start Mapping"
        elif explore_state == "EXPLORING":
            btn_text = "Mapping..."
        elif explore_state == "PAUSED":
            btn_text = "Explore More"
        else:
            btn_text = "Map Complete!"
            
        text_surf = font.render(btn_text, True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=explore_btn.center))

        pygame.display.flip()
        clock.tick(60) # Runs at 60 steps per second so you don't have to wait forever

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()