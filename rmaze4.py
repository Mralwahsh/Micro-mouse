import random
import pygame
import sys

# ==========================================
# 1. NODE-BASED CELL STRUCTURE
# ==========================================
class Cell:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.walls = {'N': True, 'S': True, 'E': True, 'W': True}
        self.visited = False

# ==========================================
# 2. MAZE GENERATION
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
# 3. PYGAME RENDERING & DIMENSION MATH
# ==========================================
def main():
    pygame.init()

    # Base grid metrics
    COLS, ROWS = 10, 10
    
    # Real-world measurements in cm
    CELL_CM = 18.0
    WALL_CM = 1.2
    
    # Calculate physical width and height
    total_walls_x = COLS - 1
    total_walls_y = ROWS - 1
    physical_width_cm = (COLS * CELL_CM) + (total_walls_x * WALL_CM)
    physical_height_cm = (ROWS * CELL_CM) + (total_walls_y * WALL_CM)
    
    # Visual mapping
    CELL_SIZE = 60 
    WALL_THICKNESS = 4 
    PADDING = 40
    
    MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + (total_walls_x * WALL_THICKNESS)
    MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + (total_walls_y * WALL_THICKNESS)
    
    WINDOW_WIDTH = MAZE_PIXEL_WIDTH + (PADDING * 2)
    # Added extra height to comfortably fit the dimension text
    WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + (PADDING * 2) + 90 

    COLOR_WALL = (200, 30, 30) 
    COLOR_FLOOR = (0, 0, 0)    
    COLOR_UI_BG = (40, 40, 40)
    COLOR_START = (30, 150, 30)
    COLOR_BUTTON = (0, 122, 204)
    COLOR_TEXT = (255, 255, 255)
    COLOR_DIMENSIONS = (180, 180, 180) # Light gray for measurements

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Precise 10x10 Micromouse Maze")
    font_bold = pygame.font.SysFont("Arial", 20, bold=True)
    font_small = pygame.font.SysFont("Arial", 16)

    maze = generate_ieee_maze()
    button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 85, 150, 40)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if button_rect.collidepoint(event.pos):
                    maze = generate_ieee_maze()

        screen.fill(COLOR_UI_BG)
        
        # Draw Floor
        pygame.draw.rect(screen, COLOR_FLOOR, (PADDING, PADDING, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))

        # Draw Start Indicator
        start_px = PADDING + WALL_THICKNESS + (0 * (CELL_SIZE + WALL_THICKNESS))
        start_py = PADDING + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
        pygame.draw.rect(screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

        # Draw Lattice Posts
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if i == 5 and j == 5:
                    continue
                px = PADDING + i * (CELL_SIZE + WALL_THICKNESS)
                py = PADDING + j * (CELL_SIZE + WALL_THICKNESS)
                pygame.draw.rect(screen, COLOR_WALL, (px, py, WALL_THICKNESS, WALL_THICKNESS))

        # Draw Walls
        for x in range(COLS):
            for y in range(ROWS):
                px = PADDING + x * (CELL_SIZE + WALL_THICKNESS)
                py = PADDING + y * (CELL_SIZE + WALL_THICKNESS)
                cell = maze[x][y]
                
                if cell.walls['N']:
                    pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py, CELL_SIZE, WALL_THICKNESS))
                if cell.walls['S']:
                    pygame.draw.rect(screen, COLOR_WALL, (px + WALL_THICKNESS, py + CELL_SIZE + WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
                if cell.walls['W']:
                    pygame.draw.rect(screen, COLOR_WALL, (px, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
                if cell.walls['E']:
                    pygame.draw.rect(screen, COLOR_WALL, (px + CELL_SIZE + WALL_THICKNESS, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))

        # UI: Draw Regenerate Button
        pygame.draw.rect(screen, COLOR_BUTTON, button_rect, border_radius=5)
        text_surf = font_bold.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=button_rect.center))

        # UI: Draw Physical Dimensions
        dim_string = f"Physical Dimensions: {physical_width_cm:.1f}cm x {physical_height_cm:.1f}cm (10 cells + 9 walls)"
        dim_surf = font_small.render(dim_string, True, COLOR_DIMENSIONS)
        dim_rect = dim_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30))
        screen.blit(dim_surf, dim_rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()