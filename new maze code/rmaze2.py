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

    # 2. Pick EXACTLY ONE entrance
    # Format: (Inside Cell, Wall to Break, Outside Cell, Opposite Wall)
    entrances = [
        ((4,4), 'N', (4,3), 'S'), ((5,4), 'N', (5,3), 'S'),
        ((4,5), 'S', (4,6), 'N'), ((5,5), 'S', (5,6), 'N'),
        ((4,4), 'W', (3,4), 'E'), ((4,5), 'W', (3,5), 'E'),
        ((5,4), 'E', (6,4), 'W'), ((5,5), 'E', (6,5), 'W')
    ]
    
    inside, dir_out, outside, dir_in = random.choice(entrances)
    grid[inside[0]][inside[1]].walls[dir_out] = False
    grid[outside[0]][outside[1]].walls[dir_in] = False
    
    # 3. Generate Maze starting from the Entrance
    # This mathematically guarantees a path to the door exists
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
            # Knock down the wall between the two cells
            grid[x][y].walls[d] = False
            opp_d = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}[d]
            grid[nx][ny].walls[opp_d] = False
            
            grid[nx][ny].visited = True
            add_walls(nx, ny)

    # 4. Add alternate routes (Loops)
    for _ in range(15):
        x = random.randint(0, cols - 1)
        y = random.randint(0, rows - 1)
        
        # Do not touch the center island's outer perimeter
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
# 3. PYGAME RENDERING (PROPER SCALE)
# ==========================================
def main():
    pygame.init()

    # Visual Scaling strictly reflecting IEEE standard
    # Cell: 18cm -> 54 pixels
    # Wall: 1.2cm -> ~4 pixels
    CELL_SIZE = 54 
    WALL_THICKNESS = 4 
    
    COLS, ROWS = 10, 10
    PADDING = 40
    WINDOW_WIDTH = (COLS * CELL_SIZE) + (PADDING * 2)
    WINDOW_HEIGHT = (ROWS * CELL_SIZE) + (PADDING * 2) + 60

    COLOR_WALL = (200, 30, 30) # Red
    COLOR_FLOOR = (0, 0, 0)    # Black
    COLOR_UI_BG = (40, 40, 40)
    COLOR_BUTTON = (0, 122, 204)
    COLOR_TEXT = (255, 255, 255)

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("IEEE Standard 10x10 Micromouse Maze")
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
        
        # Draw the black floor background for the maze area
        pygame.draw.rect(screen, COLOR_FLOOR, (PADDING, PADDING, COLS * CELL_SIZE, ROWS * CELL_SIZE))

        # Draw Start Area Indicator (Bottom Left)
        start_rect = pygame.Rect(PADDING, PADDING + (9 * CELL_SIZE), CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, (30, 150, 30), start_rect) # Dim green background for start

        # Draw Walls
        for x in range(COLS):
            for y in range(ROWS):
                px = PADDING + (x * CELL_SIZE)
                py = PADDING + (y * CELL_SIZE)
                cell = maze[x][y]
                
                # Draw lines for existing walls
                if cell.walls['N']:
                    pygame.draw.line(screen, COLOR_WALL, (px, py), (px + CELL_SIZE, py), WALL_THICKNESS)
                if cell.walls['S']:
                    pygame.draw.line(screen, COLOR_WALL, (px, py + CELL_SIZE), (px + CELL_SIZE, py + CELL_SIZE), WALL_THICKNESS)
                if cell.walls['W']:
                    pygame.draw.line(screen, COLOR_WALL, (px, py), (px, py + CELL_SIZE), WALL_THICKNESS)
                if cell.walls['E']:
                    pygame.draw.line(screen, COLOR_WALL, (px + CELL_SIZE, py), (px + CELL_SIZE, py + CELL_SIZE), WALL_THICKNESS)

                # Draw the 1.2cm lattice posts at the corners (top-left of each cell)
                pygame.draw.rect(screen, COLOR_WALL, (px - WALL_THICKNESS//2, py - WALL_THICKNESS//2, WALL_THICKNESS, WALL_THICKNESS))
        
        # Ensure bottom-right corner post of the entire maze is drawn
        pygame.draw.rect(screen, COLOR_WALL, (PADDING + COLS * CELL_SIZE - WALL_THICKNESS//2, PADDING + ROWS * CELL_SIZE - WALL_THICKNESS//2, WALL_THICKNESS, WALL_THICKNESS))

        # Draw Regenerate Button
        pygame.draw.rect(screen, COLOR_BUTTON, button_rect, border_radius=5)
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        screen.blit(text_surf, text_surf.get_rect(center=button_rect.center))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()