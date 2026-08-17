# this code make better mazes it have sub paths and have more than one path going to the same point and it have sub paths that have dead end
# this have solving algorithm that search evey single path and find the shortest path and tell you how many avaible path and the shortest one 
# this code problem that is test every single path so it so long to find the shortest path

import random
import pygame
import sys

# ==========================================
# 1. MAZE GENERATION LOGIC
# ==========================================
def generate_maze(width, height):
    grid_w = width * 2 + 1
    grid_h = height * 2 + 1
    # 1. Start with a grid full of walls
    maze = [[1] * grid_w for _ in range(grid_h)]
    
    # 2. Randomized Prim's Algorithm
    start_x, start_y = 0, 0
    maze[1][1] = 0 # Mark starting cell as path
    
    # List of walls to check: (wall_x, wall_y, neighbor_cell_x, neighbor_cell_y)
    walls = []
    walls.append((2, 1, 1, 0)) # Right wall of start
    walls.append((1, 2, 0, 1)) # Bottom wall of start
    
    visited = set([(0, 0)])
    
    while walls:
        # Pick a random wall from the list
        idx = random.randint(0, len(walls) - 1)
        wx, wy, nx, ny = walls.pop(idx)
        
        # If the cell on the other side of the wall is unvisited
        if (nx, ny) not in visited:
            # Break the wall
            maze[wy][wx] = 0
            # Make the new cell a path
            maze[ny * 2 + 1][nx * 2 + 1] = 0
            visited.add((nx, ny))
            
            # Add the new cell's neighboring walls to the list
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nnx, nny = nx + dx, ny + dy
                if 0 <= nnx < width and 0 <= nny < height and (nnx, nny) not in visited:
                    nwx, nwy = nx * 2 + 1 + dx, ny * 2 + 1 + dy
                    walls.append((nwx, nwy, nnx, nny))
                    
    # 3. Add Loops (Real Micromouse mazes have multiple paths)
    # We randomly knock down walls that separate two parallel paths
    num_loops = (width * height) // 5  # Adjust this to add more/fewer loops
    for _ in range(num_loops):
        x = random.randint(1, grid_w - 2)
        y = random.randint(1, grid_h - 2)
        
        if maze[y][x] == 1:
            # Check if it's a vertical wall between horizontal paths
            if maze[y][x-1] == 0 and maze[y][x+1] == 0 and maze[y-1][x] == 1 and maze[y+1][x] == 1:
                maze[y][x] = 0
            # Check if it's a horizontal wall between vertical paths
            elif maze[y-1][x] == 0 and maze[y+1][x] == 0 and maze[y][x-1] == 1 and maze[y][x+1] == 1:
                maze[y][x] = 0

    # Create an entrance (top-left) and exit (bottom-right)
    maze[1][0] = 0
    maze[grid_h - 2][grid_w - 1] = 0
    
    return maze

# ==========================================
# 2. MAZE SOLVING LOGIC (BFS)
# ==========================================
# ==========================================
# 2. ADVANCED SOLVER: FIND ALL PATHS & SHORTEST
# ==========================================
def find_all_paths(maze, start_x, start_y, end_x, end_y):
    all_paths = []
    
    def dfs(x, y, current_path):
        # If we reached the target, save a copy of this complete path
        if x == end_x and y == end_y:
            all_paths.append(list(current_path))
            return
            
        # Check all 4 directions
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = x + dx, y + dy
            
            # Check bounds, if it's a path (0), and not already in the current path (prevents loops)
            if 0 <= ny < len(maze) and 0 <= nx < len(maze[0]):
                if maze[ny][nx] == 0 and (nx, ny) not in current_path:
                    current_path.append((nx, ny))
                    dfs(nx, ny, current_path)
                    current_path.pop() # Backtrack when returning

    # Start the search
    dfs(start_x, start_y, [(start_x, start_y)])
    
    if not all_paths:
        return [], []
        
    # Find the shortest path(s) among all collected paths
    min_length = min(len(path) for path in all_paths)
    shortest_paths = [path for path in all_paths if len(path) == min_length]
    
    return all_paths, shortest_paths

# ==========================================
# 3. PYGAME RENDERING & UI LOGIC
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 20
    MAZE_HEIGHT = 20
    CELL_SIZE = 15
    
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
                    # 1. Get both lists from the new function
                    all_routes, shortest_routes = find_all_paths(current_maze, 0, 1, GRID_W - 1, GRID_H - 2)
                    
                    # 2. Make sure a path actually exists to prevent out-of-bounds errors
                    if shortest_routes:
                        # 3. Extract the very first shortest path to draw
                        solution_path = shortest_routes[0] 
                        
                        # Optional: Print the metrics to your console
                        print(f"Total valid paths: {len(all_routes)}")
                        print(f"Shortest path steps: {len(solution_path)}")
                    else:
                        solution_path = []

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