import random
import pygame
import sys

# ==========================================
# 1. YOUR MAZE GENERATION LOGIC
# ==========================================
def generate_maze(width, height):
    # Initialize grid with walls (1 = wall, 0 = path)
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
    maze[1][0] = 0
    maze[grid_h - 2][grid_w - 1] = 0
    
    return maze

# ==========================================
# 2. PYGAME RENDERING & UI LOGIC
# ==========================================
def main():
    pygame.init()

    # Configuration
    MAZE_WIDTH = 15  # Internal width
    MAZE_HEIGHT = 10 # Internal height
    CELL_SIZE = 20   # Pixel size of each grid square
    
    # Calculate actual grid dimensions based on your algorithm
    GRID_W = MAZE_WIDTH * 2 + 1
    GRID_H = MAZE_HEIGHT * 2 + 1
    
    # Window dimensions (add extra space at the bottom for the button)
    WINDOW_WIDTH = GRID_W * CELL_SIZE
    UI_HEIGHT = 60
    WINDOW_HEIGHT = (GRID_H * CELL_SIZE) + UI_HEIGHT

    # Colors
    COLOR_WALL = (40, 40, 40)       # Dark gray
    COLOR_PATH = (240, 240, 240)    # Off-white
    COLOR_BUTTON = (0, 122, 204)    # Blue
    COLOR_BUTTON_HOVER = (0, 153, 255)
    COLOR_TEXT = (255, 255, 255)

    # Setup display
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Micromouse Simulator")
    font = pygame.font.SysFont("Arial", 20, bold=True)

    # Generate initial maze
    current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)

    # Button properties
    button_rect = pygame.Rect(WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - UI_HEIGHT + 10, 150, 40)

    running = True
    while running:
        # 1. Handle Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Check for button clicks
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    if button_rect.collidepoint(event.pos):
                        # Regenerate the maze when clicked
                        current_maze = generate_maze(MAZE_WIDTH, MAZE_HEIGHT)

        # 2. Draw Background
        screen.fill((200, 200, 200)) # Light gray UI background

        # 3. Draw Maze
        for y, row in enumerate(current_maze):
            for x, cell in enumerate(row):
                rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if cell == 1:
                    pygame.draw.rect(screen, COLOR_WALL, rect)
                else:
                    pygame.draw.rect(screen, COLOR_PATH, rect)

        # 4. Draw Regenerate Button
        mouse_pos = pygame.mouse.get_pos()
        # Highlight button if mouse is hovering
        if button_rect.collidepoint(mouse_pos):
            pygame.draw.rect(screen, COLOR_BUTTON_HOVER, button_rect, border_radius=5)
        else:
            pygame.draw.rect(screen, COLOR_BUTTON, button_rect, border_radius=5)

        # Draw button text
        text_surf = font.render("Regenerate", True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=button_rect.center)
        screen.blit(text_surf, text_rect)

        # 5. Update Display
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()