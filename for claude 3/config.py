# config.py
import math

# Grid Dimensions
COLS, ROWS = 10, 10
CELL_SIZE = 50                 # 18.0 cm  (inside of a cell, MMRC26 rule 5.a)
WALL_THICKNESS = 3             # 1.2 cm  (post / wall thickness, rule 2.2.b)
PADDING = 30

# Real-world dimensions (single source of truth for the future physics / RL environment)
CELL_INSIDE_CM = 18.0                       # MMRC26: a cell is 18 x 18 cm measured INSIDE the walls
WALL_THICKNESS_CM = 1.2
CELL_SIZE_CM = CELL_INSIDE_CM + WALL_THICKNESS_CM   # post-to-post pitch (19.2 cm) - what the geometry uses
MOUSE_WIDTH_CM = 8.0                        # side to side
MOUSE_LENGTH_CM = 10.0                      # front to back (along the heading)
PX_PER_CM = CELL_SIZE / CELL_INSIDE_CM      # rendering scale ≈ 2.778 px/cm

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
WALL_EVIDENCE_THRESHOLD = 3             # net votes needed before an edge counts as a known WALL
OPEN_EVIDENCE_THRESHOLD = 8             # ... and as known OPEN: stricter, driving into a wall is far
                                        # worse than stopping to look once more
DRIVEN_VOTE = 8                         # "I drove through it" is strong evidence of open - but the pose
                                        # may be wrong, so it can't erase strong wall evidence
WALL_EVIDENCE_MAX = 10                  # votes saturate here so the map can still correct itself

# Drive train: two wheels on the centre line of the body (so the mouse turns on the spot)
WHEEL_DIAMETER_CM = 3.4
MOTOR_MAX_RPM = 381                     # wheel rpm after the gearbox
WHEEL_TRACK_CM = 7.0                    # distance between the two wheels (assumed - measure yours)
MAX_SPEED_CM_S = math.pi * WHEEL_DIAMETER_CM * MOTOR_MAX_RPM / 60    # ≈ 67.8 cm/s
ACCEL_CM_S2 = 200.0                     # max wheel acceleration (assumed - tune to your motors)
SEARCH_SPEED_CM_S = MAX_SPEED_CM_S      # search at full motor speed (381 rpm) through mapped cells ...
EXPLORE_SPEED_CM_S = 40.0               # ... but slow to this entering unexplored cells, so the sensors
                                        # can confirm the walls before the mouse must commit to a move
# Smooth 90-degree turns: a quarter circle through the corner cell, from the middle of the edge
# it enters by to the middle of the edge it leaves by (radius = half a cell). The outer wheel
# runs (1 + track / 2r) times faster than the mouse, so with 381 rpm motors the limit is ~50 cm/s.
TURN_RADIUS_CM = 9.6                    # = CELL_SIZE_CM / 2
# fastest corner the motors allow: the OUTER wheel at 381 rpm (~49.7 cm/s, 0.26 g sideways)
CORNER_SPEED_CM_S = MAX_SPEED_CM_S / (1 + WHEEL_TRACK_CM / (2 * TURN_RADIUS_CM))
SEARCH_TURN_SPEED_CM_S = CORNER_SPEED_CM_S
FAST_TURN_SPEED_CM_S = CORNER_SPEED_CM_S
MOTOR_LAG_COMP_S = 0.03                 # firmware: measured motor response time; corners start/end this early
ARC_K_RADIUS = 0.4                      # rad/s of extra turn per cm off the ideal arc
ARC_K_HEADING = 8.0                     # rad/s per rad off the arc's tangent
# Turning on the spot spins the wheels in opposite directions, so the same wheel limits apply
MAX_TURN_RAD_S = 2 * MAX_SPEED_CM_S / WHEEL_TRACK_CM
TURN_ACCEL_RAD_S2 = 2 * ACCEL_CM_S2 / WHEEL_TRACK_CM

# Reality gap (simulation only - the firmware cannot see these): the body never moves exactly as commanded
WHEEL_MISMATCH = 0.005                  # std-dev of each wheel's real/assumed diameter ratio (fixed per robot)
WHEEL_SLIP_NOISE = 0.03                 # random slip on each wheel, every physics tick
START_POS_ERROR_CM = 0.5                # hand-placement error at the start
START_ANGLE_ERROR_DEG = 2.0
MOTOR_TAU_S = 0.03                      # motors reach ~63% of a new speed command after this long
SENSOR_LATENCY_S = 0.02                 # a TOF reading describes where the body was this long ago

# Centering (firmware, encoders only - no IMU): an observer estimates offset, heading error and
# the robot's own wheel-mismatch curve from the steering it commands + the side-wall distances
CENTER_KP = 1.2                         # rad/s of steering per cm off-centre (tuned for 381 rpm straights)
CENTER_KH = 14.0                        # rad/s of steering per rad of heading error
MAX_STEER_RAD_S = 2.0
OBS_K_OFFSET = 0.3                      # observer gains, applied per side-wall reading
OBS_K_HEADING = 0.02                    # rad per cm of reading error
OBS_K_CURVE = 0.0002                    # (rad/cm) per cm of reading error

# Simulation timing
PHYSICS_HZ = 200                        # physics / control loop rate
SIM_SPEEDS = [0.25, 0.5, 1, 2, 4, 8]    # playback multipliers (Up/Down arrows)
DEFAULT_SIM_SPEED = 1

# Movement helpers (shared by maze.py and micromouse.py)
DIRECTIONS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
TARGET_CELLS = {(4, 4), (5, 4), (4, 5), (5, 5)}
START_CELL = (0, ROWS - 1)                  # bottom-left corner; its only opening is North (the next cell clockwise)
MAZE_EXTRA_OPENINGS = 6                     # walls knocked out after carving, for the loops rule 5.e expects

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