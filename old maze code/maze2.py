# this code generate maze with one path and its vary long but it does not have sub paths that might have dead end

import random
import pygame
import sys

# ==========================================
# 1. MAZE GENERATION LOGIC
# ==========================================
def generate_maze(width, height):
    grid_w = width * 2 + 1
    grid_h = height * 2 + 1
    maze = [[1] * grid_w for _ in range(grid_h)]
    
    visited = set()
    
    def carve_path(cx, cy):
        visited.add((cx, cy))
        maze[cy * 2 + 1][cx * 2 + 1] = 0
        
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        random.shuffle(directions)
        
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                maze[cy * 2 + 1 + dy][cx * 2 + 1 + dx] = 0
                carve_path(nx, ny)

    carve_path(0, 0)
    
    # Entrance and Exit
    maze[1][0] = 0
    maze[grid_h - 2][grid_w - 1] = 0
    
    return maze

# ==========================================
# 2. MAZE SOLVING LOGIC (BFS)
# ==========================================
def solve_maze(maze, start_x, start_y, end_x, end_y):
    # Queue stores the paths taken so far
    queue = [[(start_x, start_y)]]
    visited = set([(start_x, start_y)])
    
    while queue:
        # Get the first path in the queue
        current_path = queue.pop(0)
        x, y = current_path[-1]
        
        # If we reached the end, return the path that got us here
        if x == end_x and y == end_y:
            return current_path
            
        # Check all 4 adjacent directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            
            # If within bounds, is a path (0), and hasn't been visited
            if 0 <= ny < len(maze) and 0 <= nx < len(maze[0]):
                if maze[ny][nx] == 0 and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    
                    # Create a new path with this next step and add to queue
                    new_path = list(current_path)
                    new_path.append((nx, ny))
                    queue.append(new_path)
                    
    return [] # Return empty if no path exists (won't happen with perfect mazes)

# ==========================================
# 3. PYGAME RENDERING & UI LOGIC
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 15
    MAZE_HEIGHT = 10
    CELL_SIZE = 20
    
    GRID_W = MAZE_WIDTH * 2 + 1
    GRID_H = MAZE_HEIGHT * 2 + 1
    
    WINDOW_WIDTH = max(GRID_W * CELL_SIZE, 400)
    UI_HEIGHT = 80
    WINDOW_HEIGHT = (GRID_H * CELL_SIZE) + UI_HEIGHT

    # Colors
    COLOR_WALL = (40, 40, 40)
    COLOR_PATH = (240, 240, 240)
    COLOR_SOLUTION = (220, 50, 50)  # Red line for the path
    COLOR_BUTTON = (0, 122, 204)
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Micromouse Simulator - Solver")
    font = pygame.font.SysFont("Arial", 18, bold=True)

    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
    solution_path = []

    # Button Layout
    regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)
    solve_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - UI_HEIGHT + 20, 140, 40)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if regen_btn.collidepoint(event.pos):
                    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)
                    solution_path = [] # Clear previous path
                elif solve_btn.collidepoint(event.pos):
                    # Start at entrance (0, 1) and end at exit (GRID_W-1, GRID_H-2)
                    solution_path = solve_maze(current_maze, 0, 1, GRID_W - 1, GRID_H - 2)

        screen.fill((200, 200, 200))

        # Draw Maze
        for y, row in enumerate(current_maze):
            for x, cell in enumerate(row):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                color = COLOR_WALL if cell == 1 else COLOR_PATH
                pygame.draw.rect(screen, color, rect)

        # Draw Solution Path
        if solution_path:
            for i in range(len(solution_path) - 1):
                x1, y1 = solution_path[i]
                x2, y2 = solution_path[i+1]
                
                # Calculate center points of the cells to draw a nice line
                start_pos = (x1 * CELL_SIZE + CELL_SIZE // 2, y1 * CELL_SIZE + CELL_SIZE // 2)
                end_pos = (x2 * CELL_SIZE + CELL_SIZE // 2, y2 * CELL_SIZE + CELL_SIZE // 2)
                
                pygame.draw.line(screen, COLOR_SOLUTION, start_pos, end_pos, 4)

        # Draw Buttons
        mouse_pos = pygame.mouse.get_pos()
        
        # Regenerate Button
        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, regen_btn, border_radius=5)
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=regen_btn.center))

        # Solve Button
        pygame.draw.rect(screen, COLOR_BUTTON_HOVER if solve_btn.collidepoint(mouse_pos) else COLOR_BUTTON, solve_btn, border_radius=5)
        text_surf = font.render("Solve", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=solve_btn.center))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()