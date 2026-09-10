# config.py

# Grid Dimensions
COLS, ROWS = 10, 10
CELL_SIZE = 30                 # 18.0 cm  (IEEE standard cell pitch)
WALL_THICKNESS = 2             # 1.2 cm  (IEEE standard wall thickness)
PADDING = 30

# Real-world dimensions (single source of truth for the future physics / RL environment)
CELL_SIZE_CM = 18.0
WALL_THICKNESS_CM = 1.2
PX_PER_CM = CELL_SIZE / CELL_SIZE_CM        # rendering scale ≈ 1.667 px/cm

# Movement helpers (shared by maze.py and micromouse.py)
DIRECTIONS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
TARGET_CELLS = {(4, 4), (5, 4), (4, 5), (5, 5)}
START_CELL = (0, ROWS - 1)

# Pixel Dimensions
MAZE_PIXEL_WIDTH = (COLS * CELL_SIZE) + ((COLS + 1) * WALL_THICKNESS)
MAZE_PIXEL_HEIGHT = (ROWS * CELL_SIZE) + ((ROWS + 1) * WALL_THICKNESS)
WINDOW_WIDTH = (MAZE_PIXEL_WIDTH * 4) + (PADDING * 5)
WINDOW_HEIGHT = MAZE_PIXEL_HEIGHT + 160 

# Colors
COLOR_WALL_RED = (200, 30, 30) 
COLOR_WALL_BLUE = (30, 100, 255) 
COLOR_FLOOR = (0, 0, 0)    
COLOR_UI_BG = (40, 40, 40)
COLOR_FOG = (20, 20, 20)
COLOR_START = (30, 150, 30)
COLOR_PHYSICAL_MOUSE = (0, 150, 255) 
COLOR_MEMORY_MOUSE = (0, 255, 0)     
COLOR_VISITED_TRAIL = (70, 0, 130)   
COLOR_SOLUTION = (255, 0, 0)         
COLOR_BUTTON = (0, 122, 204)
COLOR_BUTTON_HOVER = (0, 153, 255)
COLOR_TEXT_METRIC = (180, 220, 255)