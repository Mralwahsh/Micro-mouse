import random
import pygame
import sys

# ==========================================
# 1. MAZE GENERATION (Randomized Prim's + Loops)
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
                    
    num_loops = (width * height) // 5
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
# 2. PYGAME RENDERING & SINGLE MOUSE LOGIC
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 15
    MAZE_HEIGHT = 10
    CELL_SIZE = 20
    
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
    COLOR_MOUSE = (0, 150, 255) # Blue color for our physical mouse
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Micromouse Simulator - Single Agent Mapping")
    font = pygame.font.SysFont("Arial", 18, bold=True)
    title_font = pygame.font.SysFont("Arial", 22, bold=True)

    # State variables
    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
    
    is_exploring = False
    solution_path = []
    
    # Mouse state
    mouse_x, mouse_y = 0, 1
    path_stack = [] # Acts as the physical path the mouse is currently driving on
    visited = set()
    
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)
    explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)

    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if regen_btn.collidepoint(event.pos):
                    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
                    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
                    is_exploring = False
                    solution_path = []
                    
                elif explore_btn.collidepoint(event.pos) and not is_exploring:
                    is_exploring = True
                    solution_path = []
                    mouse_x, mouse_y = 0, 1
                    path_stack = [(mouse_x, mouse_y)]
                    visited = set([(mouse_x, mouse_y)])
                    
        # --- EXPLORATION LOGIC (Single Agent DFS) ---
        if is_exploring:
            end_x, end_y = GRID_W - 1, GRID_H - 2
            
            if mouse_x == end_x and mouse_y == end_y:
                # Reached the end! The stack represents the shortest path found.
                solution_path = list(path_stack)
                is_exploring = False
            else:
                # 1. Update Mouse Sensors (Reveal current cell and 4 adjacent neighbors)
                mouse_memory[mouse_y][mouse_x] = current_maze[mouse_y][mouse_x]
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W:
                        mouse_memory[ny][nx] = current_maze[ny][nx]
                
                # 2. Look for open, unvisited neighbors based on sensor data
                unvisited_neighbors = []
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = mouse_x + dx, mouse_y + dy
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W:
                        # If the memory says it's a path and we haven't been there
                        if mouse_memory[ny][nx] == 0 and (nx, ny) not in visited:
                            unvisited_neighbors.append((nx, ny))
                
                if unvisited_neighbors:
                    # Drive forward to the first available open neighbor
                    next_x, next_y = unvisited_neighbors[0]
                    mouse_x, mouse_y = next_x, next_y
                    visited.add((mouse_x, mouse_y))
                    path_stack.append((mouse_x, mouse_y))
                else:
                    # DEAD END! Physically drive backward (pop from stack)
                    if len(path_stack) > 1:
                        path_stack.pop() # Remove current bad position
                        mouse_x, mouse_y = path_stack[-1] # Move back to the previous intersection
                    else:
                        is_exploring = False # Completely stuck, nowhere to go

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

        # Draw the final solution path if finished
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                start_pos = (right_offset + (x1 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y1 * CELL_SIZE) + CELL_SIZE // 2)
                end_pos = (right_offset + (x2 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y2 * CELL_SIZE) + CELL_SIZE // 2)
                pygame.draw.line(screen, COLOR_SOLUTION, start_pos, end_pos, 4)

        # Draw the physical Mouse on the right grid (only while exploring)
        if is_exploring:
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
        btn_text = "Exploring..." if is_exploring else "Start Mapping"
        text_surf = font.render(btn_text, True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=explore_btn.center))

        pygame.display.flip()
        # Adjust this number to make the mouse move faster or slower (FPS)
        clock.tick(30) 

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()