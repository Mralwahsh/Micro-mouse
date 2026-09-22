# config.py

# Grid Dimensions
COLS, ROWS = 10, 10
CELL_SIZE = 50                 # 18.0 cm  (IEEE standard cell pitch)
WALL_THICKNESS = 3             # 1.2 cm  (IEEE standard wall thickness)
PADDING = 30

# Real-world dimensions (single source of truth for the future physics / RL environment)
CELL_SIZE_CM = 18.0
WALL_THICKNESS_CM = 1.2
MOUSE_WIDTH_CM = 8.0                        # side to side
MOUSE_LENGTH_CM = 10.0                      # front to back (along the heading)
PX_PER_CM = CELL_SIZE / CELL_SIZE_CM        # rendering scale ≈ 2.778 px/cm

# Sensor layout, in the mouse body frame (cm, origin = body centre):
#   x = to the right of centre, y = forward of centre,
#   angle = degrees from straight ahead (positive = towards the right), range = max reach.
# The two angled TOFs sit at the rear corners and look diagonally ACROSS the body,
# so their beams cross at the centre (rear-left looks front-right and vice versa).
SENSORS = [
    {"name": "Left IR",         "short": "L-IR", "kind": "IR",  "x": -3.5, "y":  0.5, "angle": -90, "range": 2.5},
    {"name": "Right IR",        "short": "R-IR", "kind": "IR",  "x":  3.5, "y":  0.5, "angle":  90, "range": 2.5},
    {"name": "Front TOF",       "short": "F",    "kind": "TOF", "x":  0.0, "y": -4.2, "angle":   0, "range": 80.0},
    {"name": "Front-Right TOF", "short": "FR",   "kind": "TOF", "x": -3.0, "y": -3.5, "angle":  45, "range": 80.0},
    {"name": "Front-Left TOF",  "short": "FL",   "kind": "TOF", "x":  3.0, "y": -3.5, "angle": -45, "range": 80.0},
]

# Sensor behaviour: sampling rate and noise (distance readings only - no ground truth leaks out)
SENSOR_HZ = 50                          # how often all sensors are read
TOF_NOISE_CM = 0.5                      # TOF std-dev = TOF_NOISE_CM + TOF_NOISE_FRAC * distance
TOF_NOISE_FRAC = 0.015
IR_NOISE_CM = 0.1
SENSOR_DROPOUT = 0.005                  # chance a reading comes back as "out of range" anyway

# Mapping: walls are decided by accumulated evidence, not a single reading
WALL_EVIDENCE_THRESHOLD = 3             # net votes needed before an edge counts as known
WALL_EVIDENCE_MAX = 10                  # votes saturate here so the map can still correct itself

# Motion limits for the search run (continuous driving between cells)
MAX_SPEED_CM_S = 50.0
ACCEL_CM_S2 = 100.0
MAX_TURN_DEG_S = 360.0
TURN_ACCEL_DEG_S2 = 1440.0

# Simulation timing
PHYSICS_HZ = 200                        # physics / control loop rate
SIM_SPEEDS = [0.25, 0.5, 1, 2, 4, 8]    # playback multipliers (Up/Down arrows)
DEFAULT_SIM_SPEED = 1

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
COLOR_LEAST_TURN = (0, 230, 0)       # least-turn path overlay (panel 4)
COLOR_BUTTON = (0, 122, 204)
COLOR_BUTTON_HOVER = (0, 153, 255)
COLOR_TEXT_METRIC = (180, 220, 255)