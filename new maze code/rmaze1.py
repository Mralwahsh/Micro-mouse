import random
import pygame
import sys

def generate_ieee_maze():
    width, height = 10, 10
    grid_w = width * 2 + 1
    grid_h = height * 2 + 1
    
    # 1. Initialize grid with walls (1 = wall, 0 = path)
    maze = [[1] * grid_w for _ in range(grid_h)]
    visited = set()
    
    # 2. Build the Center 2x2 Island (Cells 4,4 to 5,5)
    # Array indices for the center: x from 9 to 11, y from 9 to 11
    for y in range(9, 12):
        for x in range(9, 12):
            maze[y][x] = 0 # Hollow out the center room
            
    # 3. Create the "Island" Path Ring
    # To prevent wall-hugging, the walls enclosing the center (x=8,12 and y=8,12) 
    # must be surrounded by a guaranteed path ring (x=7,13 and y=7,13).
    for i in range(7, 14):
        maze[7][i] = 0  # Top path ring
        maze[13][i] = 0 # Bottom path ring
        maze[i][7] = 0  # Left path ring
        maze[i][13] = 0 # Right path ring
        
        # Add these path ring cells to 'visited' so Prim's algorithm connects to them
        if i % 2 != 0:
            visited.add((i//2, 7//2))
            visited.add((i//2, 13//2))
            visited.add((7//2, i//2))
            visited.add((13//2, i//2))

    # 4. Create EXACTLY ONE entrance to the center room
    entrances = [(8, 10), (12, 10), (10, 8), (10, 12)]
    door_x, door_y = random.choice(entrances)
    maze[door_y][door_x] = 0

    # 5. Randomized Prim's Algorithm for the rest of the maze
    # Start generating from the bottom-left corner (IEEE standard start)
    start_x, start_y = 0, 9 
    maze[19][1] = 0
    visited.add((start_x, start_y))
    
    walls = []
    # Add initial walls of the start cell
    walls.append((2, 19, 1, 9)) # Right wall
    walls.append((1, 18, 0, 8)) # Top wall

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

    # 6. Add Loops (Multiple routes to the center)
    num_loops = 15
    for _ in range(num_loops):
        x = random.randint(1, grid_w - 2)
        y = random.randint(1, grid_h - 2)
        
        # Don't break the center room's solid walls (except the 1 entrance)
        if 8 <= x <= 12 and 8 <= y <= 12:
            continue
            
        if maze[y][x] == 1:
            if maze[y][x-1] == 0 and maze[y][x+1] == 0 and maze[y-1][x] == 1 and maze[y+1][x] == 1:
                maze[y][x] = 0
            elif maze[y-1][x] == 0 and maze[y+1][x] == 0 and maze[y][x-1] == 1 and maze[y][x+1] == 1:
                maze[y][x] = 0
                
    return maze

def main():
    pygame.init()

    # Visual Scaling
    CELL_SIZE = 35 # Made slightly larger since it's a 10x10 grid now
    GRID_W = 10 * 2 + 1
    GRID_H = 10 * 2 + 1
    
    WINDOW_WIDTH = GRID_W * CELL_SIZE
    WINDOW_HEIGHT = GRID_H * CELL_SIZE + 60

    # Colors based on IEEE spec
    COLOR_WALL_TOP = (200, 30, 30) # Red walls
    COLOR_FLOOR = (0, 0, 0)        # Black floor
    COLOR_UI_BG = (40, 40, 40)
    COLOR_BUTTON = (0, 122, 204)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Standard Micromouse Maze")
    font = pygame.font.SysFont("Arial", 20, bold=True)

    current_maze = generate_ieee_maze()
    button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 50, 150, 40)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if button_rect.collidepoint(event.pos):
                    current_maze = generate_ieee_maze()

        screen.fill(COLOR_UI_BG)

        # Draw Maze
        for y, row in enumerate(current_maze):
            for x, cell in enumerate(row):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if cell == 1:
                    pygame.draw.rect(screen, COLOR_WALL_TOP, rect)
                else:
                    pygame.draw.rect(screen, COLOR_FLOOR, rect)

        # Draw Start Area Indicator (Bottom Left)
        start_rect = pygame.Rect(1 * CELL_SIZE, 19 * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, (50, 200, 50), start_rect, 3) # Green outline for start

        # Draw Button
        pygame.draw.rect(screen, COLOR_BUTTON, button_rect, border_radius=5)
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=button_rect.center))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()