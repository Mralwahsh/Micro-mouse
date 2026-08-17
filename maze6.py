import random
import pygame
import sys
from collections import deque

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
# 2. PYGAME RENDERING & DUAL-SCREEN LOGIC
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 20
    MAZE_HEIGHT = 20
    CELL_SIZE = 15
    
    GRID_W = MAZE_WIDTH * 2 + 1
    GRID_H = MAZE_HEIGHT * 2 + 1
    
    # Double the width to fit two mazes, plus a 40px gap in the middle
    MAZE_PIXEL_WIDTH = GRID_W * CELL_SIZE
    WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 2) + 40
    UI_HEIGHT = 80
    WINDOW_HEIGHT = (GRID_H * CELL_SIZE) + UI_HEIGHT

    # Colors
    COLOR_WALL = (40, 40, 40)
    COLOR_PATH = (240, 240, 240)
    COLOR_UNKNOWN = (0, 0, 0)       # Black for undiscovered areas
    COLOR_SOLUTION = (220, 50, 50)
    COLOR_EXPLORE = (100, 200, 100) # Green for cells currently in queue
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Micromouse Simulator - Dual Mapping")
    font = pygame.font.SysFont("Arial", 18, bold=True)
    title_font = pygame.font.SysFont("Arial", 22, bold=True)

    # Initial State
    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
    # Create the mouse's memory map filled with 2 (which means "unknown/black")
    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
    
    # Exploration state variables
    is_exploring = False
    solution_path = []
    queue = deque()
    visited = set()
    
    # Buttons
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
                    # Reset everything
                    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
                    mouse_memory = [[2 for _ in range(GRID_W)] for _ in range(GRID_H)]
                    is_exploring = False
                    solution_path = []
                    queue.clear()
                    visited.clear()
                    
                elif explore_btn.collidepoint(event.pos) and not is_exploring:
                    # Start exploration
                    is_exploring = True
                    solution_path = []
                    start_x, start_y = 0, 1
                    queue = deque([(start_x, start_y, [(start_x, start_y)])])
                    visited = set([(start_x, start_y)])
                    # Mouse discovers its starting location
                    mouse_memory[start_y][start_x] = current_maze[start_y][start_x]

        # --- EXPLORATION LOGIC (Runs 1 step per frame) ---
        if is_exploring and queue:
            # We process a few cells per frame to make the animation speed reasonable
            for _ in range(3): 
                if not queue:
                    break
                    
                x, y, current_path = queue.popleft()
                
                # Target coordinates
                end_x, end_y = GRID_W - 1, GRID_H - 2
                
                if x == end_x and y == end_y:
                    solution_path = current_path
                    is_exploring = False
                    break
                    
                for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    
                    if 0 <= ny < GRID_H and 0 <= nx < GRID_W:
                        # The mouse's sensors detect the block and write it to memory
                        mouse_memory[ny][nx] = current_maze[ny][nx]
                        
                        if current_maze[ny][nx] == 0 and (nx, ny) not in visited:
                            visited.add((nx, ny))
                            queue.append((nx, ny, current_path + [(nx, ny)]))

        # --- DRAWING ---
        screen.fill((200, 200, 200))

        # Helper function to draw a single grid
        def draw_grid(maze_data, offset_x, title):
            # Draw title
            text_surf = title_font.render(title, True, (0,0,0))
            screen.blit(text_surf, (offset_x, 10))
            
            # Draw cells
            for y, row in enumerate(maze_data):
                for x, cell in enumerate(row):
                    rect = pygame.Rect(offset_x + (x * CELL_SIZE), 40 + (y * CELL_SIZE), CELL_SIZE, CELL_SIZE)
                    if cell == 1:
                        pygame.draw.rect(screen, COLOR_WALL, rect)
                    elif cell == 0:
                        pygame.draw.rect(screen, COLOR_PATH, rect)
                    elif cell == 2:
                        pygame.draw.rect(screen, COLOR_UNKNOWN, rect)

        # Draw Left Grid (Ground Truth)
        draw_grid(current_maze, 10, "Physical Maze (Ground Truth)")
        
        # Draw Right Grid (Mouse's Map Memory)
        right_offset = MAZE_PIXEL_WIDTH + 30
        draw_grid(mouse_memory, right_offset, "Mouse's Memory Map")

        # Draw Solution Path (on the right grid)
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                start_pos = (right_offset + (x1 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y1 * CELL_SIZE) + CELL_SIZE // 2)
                end_pos = (right_offset + (x2 * CELL_SIZE) + CELL_SIZE // 2, 40 + (y2 * CELL_SIZE) + CELL_SIZE // 2)
                pygame.draw.line(screen, COLOR_SOLUTION, start_pos, end_pos, 4)

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
        clock.tick(60) # Limit to 60 FPS

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()