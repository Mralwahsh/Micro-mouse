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
        # Every cell starts completely walled in
        self.walls = {'N': True, 'S': True, 'E': True, 'W': True}
        self.visited = False

# ==========================================
# 2. MAZE GENERATION
# ==========================================
def generate_ieee_maze():
    cols, rows = 10, 10
    grid = [[Cell(x, y) for y in range(rows)] for x in range(cols)]
    
    # The 2x2 Center Island 
    center_cells = [(4, 4), (5, 4), (4, 5), (5, 5)]
    
    # 1. Hollow out the center room by removing internal walls
    grid[4][4].walls['E'] = False; grid[5][4].walls['W'] = False
    grid[4][4].walls['S'] = False; grid[4][5].walls['N'] = False
    grid[5][4].walls['S'] = False; grid[5][5].walls['N'] = False
    grid[4][5].walls['E'] = False; grid[5][5].walls['W'] = False
    
    for cx, cy in center_cells:
        grid[cx][cy].visited = True # Mark as visited so algorithm ignores them

    # 2. Pick EXACTLY ONE entrance for the island
    entrances = [
        ((4,4), 'N', (4,3), 'S'), ((5,4), 'N', (5,3), 'S'),
        ((4,5), 'S', (4,6), 'N'), ((5,5), 'S', (5,6), 'N'),
        ((4,4), 'W', (3,4), 'E'), ((4,5), 'W', (3,5), 'E'),
        ((5,4), 'E', (6,4), 'W'), ((5,5), 'E', (6,5), 'W')
    ]
    
    inside, dir_out, outside, dir_in = random.choice(entrances)
    grid[inside[0]][inside[1]].walls[dir_out] = False
    grid[outside[0]][outside[1]].walls[dir_in] = False
    
    # 3. Generate Maze starting from the Entrance to guarantee connectivity
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
    
    # Randomized Prim's Algorithm
    while walls_list:
        idx = random.randint(0, len(walls_list) - 1)
        x, y, nx, ny, d = walls_list.pop(idx)
        
        if not grid[nx][ny].visited:
            # Knock down the wall physically between the two cells
            grid[x][y].walls[d] = False
            opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
            grid[nx][ny].walls[opp_d] = False
            
            grid[nx][ny].visited = True
            add_walls(nx, ny)

    # 4. Add alternate routes (Loops)
    for _ in range(15):
        x = random.randint(0, cols - 1)
        y = random.randint(0, rows - 1)
        
        if (x, y) in center_cells: continue
        
        d = random.choice(['N', 'S', 'E', 'W'])
        dx, dy = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}[d]
        nx, ny = x + dx, y + dy
        
        # Break wall if neighbor is valid and not in the center island
        if 0 <= nx < cols and 0 <= ny < rows:
            if (nx, ny) in center_cells: continue
            
            grid[x][y].walls[d] = False
            opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
            grid[nx][ny].walls[opp_d] = False

    return grid

# ==========================================
# 3. PYGAME RENDERING (PROPER IEEE SCALE)
# ==========================================
def main():
    pygame.init()

    # MATH: Cell interior is strictly 18cm (60 pixels). Walls are 1.2cm (4 pixels).
    # Walls are drawn as separate blocks of space outside the 60px cell interior.
    CELL_SIZE = 60 
    WALL_THICKNESS = 4 
    
    COLS, ROWS = 10, 10
    PADDING = 40
    
    # Total dimension is 10 cells PLUS the 11 walls that separate/enclose them
    MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + ((COLS + 1) * WALL_THICKNESS)
    MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + ((ROWS + 1) * WALL_THICKNESS)
    
    WINDOW_WIDTH = MAZE_PIXEL_WIDTH + (PADDING * 2)
    WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + (PADDING * 2) + 60

    COLOR_WALL = (200, 30, 30) # Red wall tops
    COLOR_FLOOR = (0, 0, 0)    # Black floor
    COLOR_UI_BG = (40, 40, 40)
    COLOR_START = (30, 150, 30)
    COLOR_BUTTON = (0, 122, 204)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Precise 10x10 Micromouse Maze")
    font = pygame.font.SysFont("Arial", 20, bold=True)

    maze = generate_ieee_maze()
    button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 60, 150, 40)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if button_rect.collidepoint(event.pos):
                    maze = generate_ieee_maze()

        screen.fill(COLOR_UI_BG)
        
        # 1. Draw the Black Floor Background exactly covering the maze area
        pygame.draw.rect(screen, COLOR_FLOOR, (PADDING, PADDING, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))

        # 2. Draw Start Area Indicator (Bottom Left Cell: 0, 9)
        start_px = PADDING + WALL_THICKNESS + (0 * (CELL_SIZE + WALL_THICKNESS))
        start_py = PADDING + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
        pygame.draw.rect(screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

        # 3. Draw Lattice Posts (1.2cm corners)
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                # Omit the post in the exact center of the 2x2 destination goal
                if i == 5 and j == 5:
                    continue
                
                px = PADDING + i * (CELL_SIZE + WALL_THICKNESS)
                py = PADDING + j * (CELL_SIZE + WALL_THICKNESS)
                pygame.draw.rect(screen, COLOR_WALL, (px, py, WALL_THICKNESS, WALL_THICKNESS))

        # 4. Draw Walls (Seamlessly connecting the lattice posts)
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

        # 5. Draw Regenerate Button
        pygame.draw.rect(screen, COLOR_BUTTON, button_rect, border_radius=5)
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=button_rect.center))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()