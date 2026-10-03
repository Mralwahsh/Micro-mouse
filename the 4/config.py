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
MOUSE_WIDTH_CM = 7.0                        # side to side
MOUSE_LENGTH_CM = 10.0                      # front to back (along the heading)
PX_PER_CM = CELL_SIZE / CELL_INSIDE_CM      # rendering scale ≈ 2.778 px/cm

# Sensor behaviour, as the real parts are (the firmware only ever gets a noisy distance)
TOF_MEASURE_S = 0.025                   # a TOF needs 25 ms per reading -> 40 readings a second. The value
                                        # is an average over those 25 ms, so it describes where the mouse
                                        # was ~12.5 ms before it arrives
IR_MEASURE_S = 0.005                    # the analog side IRs are fast: sampled every 5 ms
TOF_ACCURACY = 0.85                     # a TOF reads within +/-15 % of the true distance (95 % of readings)
IR_ACCURACY = 0.95                      # an IR reads within +/-5 %
MIN_NOISE_CM = 0.1                      # the noise never gets smaller than this, however close
SENSOR_DROPOUT = 0.005                  # chance a reading comes back as "out of range" anyway

# Sensor layout, in the mouse body frame (cm, origin = body centre):
#   x = to the right of centre, y = forward of centre,
#   angle = degrees from straight ahead (positive = towards the right), range = max reach,
#   period = time between readings, latency = how old the pose a reading describes is.
# The two angled TOFs sit at the rear corners and look diagonally ACROSS the body,
# so their beams cross at the centre (rear-left looks front-right and vice versa).
# side IR range 6.5 cm (upgraded from 3.5): the side wall is 5.5 cm from each IR when the mouse is
# centred, so above 5.5 cm the IRs see both side walls all the time - crashes drop to ~0
_IR = {"kind": "IR", "range": 6.5, "accuracy": IR_ACCURACY, "period": IR_MEASURE_S, "latency": 0.0}
_TOF = {"kind": "TOF", "range": 80.0, "accuracy": TOF_ACCURACY, "period": TOF_MEASURE_S,
        "latency": TOF_MEASURE_S / 2}
SENSORS = [
    {"name": "Left IR",         "short": "L-IR", "x": -3.5, "y":  0.5, "angle": -90, **_IR},
    {"name": "Right IR",        "short": "R-IR", "x":  3.5, "y":  0.5, "angle":  90, **_IR},
    {"name": "Front TOF",       "short": "F",    "x":  0.0, "y": -4.2, "angle":   0, **_TOF},
    {"name": "Front-Right TOF", "short": "FR",   "x": -3.0, "y": -3.5, "angle":  45, **_TOF},
    {"name": "Front-Left TOF",  "short": "FL",   "x":  3.0, "y": -3.5, "angle": -45, **_TOF},
]

# Mapping: walls are decided by accumulated evidence, not a single reading
WALL_EVIDENCE_THRESHOLD = 3             # net votes needed before an edge counts as a known WALL
OPEN_EVIDENCE_THRESHOLD = 8             # ... and as known OPEN: stricter, driving into a wall is far
                                        # worse than stopping to look once more
DRIVEN_VOTE = 8                         # "I drove through it" is strong evidence of open - but the pose
                                        # may be wrong, so it can't erase strong wall evidence
WALL_EVIDENCE_MAX = 10                  # votes saturate here so the map can still correct itself

# Drive train: two wheels on the centre line of the body (so the mouse turns on the spot)
WHEEL_DIAMETER_CM = 4.4
MOTOR_MAX_RPM = 381                     # wheel rpm after the gearbox
WHEEL_TRACK_CM = 7.0                    # distance between the two wheels (assumed - measure yours)
MAX_SPEED_CM_S = math.pi * WHEEL_DIAMETER_CM * MOTOR_MAX_RPM / 60    # 44 mm wheels at 381 rpm: ≈ 87.8 cm/s
ACCEL_CM_S2 = 200.0                     # max wheel acceleration (assumed - tune to your motors)
SEARCH_SPEED_CM_S = MAX_SPEED_CM_S      # search at full motor speed (381 rpm) through mapped cells ...
EXPLORE_SPEED_CM_S = 40.0               # ... but slow to this entering unexplored cells, so the sensors
                                        # can confirm the walls before the mouse must commit to a move
# Smooth 90-degree turns: a quarter circle through the corner cell, from the middle of the edge
# it enters by to the middle of the edge it leaves by (radius = half a cell). The outer wheel
# runs (1 + track / 2r) times faster than the mouse, so with 381 rpm motors the limit is ~50 cm/s.
TURN_RADIUS_CM = 9.6                    # = CELL_SIZE_CM / 2
MAX_SIDEWAYS_G = 0.5                    # tyre grip on painted plywood (rule 5.b: "may be quite slick")


def corner_speed(radius_cm):
    """Top speed on an arc of this radius: the outer wheel runs (1 + track / 2r) times faster and
    must stay within the motors' rpm, and the sideways pull v^2 / r must stay within the tyres' grip."""
    motors = MAX_SPEED_CM_S / (1 + WHEEL_TRACK_CM / (2 * radius_cm))
    grip = math.sqrt(MAX_SIDEWAYS_G * 981.0 * radius_cm)
    return min(motors, grip)


# with 44 mm wheels: ~64 / 71 / 74 cm/s for radius 9.6 / 14.4 / 19.2 cm (the standard corner
# pulls ~0.44 g sideways, close to MAX_SIDEWAYS_G)


CORNER_SPEED_CM_S = corner_speed(TURN_RADIUS_CM)
# Fast runs only (the route is known): faster geometry where the route allows it
BIG_CORNERS = True                      # a corner with straights on both sides is swept wider ...
BIG_TURN_RADIUS_CM = 14.4               # ... faster than a standard corner; the inner post clears the body by ~3.3 cm
DIAGONALS = True                        # staircases (corners alternating left/right) are cut with a
                                        # 45-degree diagonal through the middles of the cell edges
DIAG_TURN_RADIUS_CM = 19.2              # the 45-degree curves onto / off the diagonal
DIAG_HERO_ONLY = 1                      # 1: use diagonals only until ONE diagonal run succeeds - that
                                        # sets the best time - then race without them (fewer crashes)
DIAG_SPEED_CM_S = MAX_SPEED_CM_S        # full speed on the diagonal (posts pass ~2.4 cm from the 7 cm body)
DIAG_KP = 1.2                           # steering back onto the diagonal line (rad/s per cm) ...
DIAG_KH = 14.0                          # ... and onto its direction (rad/s per rad)
DIAG_POS_GAIN = 0.3                     # position fix per wall / post reading while on the diagonal
DIAG_HEAD_GAIN = 0.02                   # ... and heading fix per cm of sideways position fix (rad/cm)
DIAG_USE_CURVE = 1                      # apply the learned wheel-mismatch curve on the diagonal (1/0)
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
START_SPOT_SIDE_CM = 4.0                # the operator sets it down anywhere in the start cell: up to
START_SPOT_ALONG_CM = 3.0               # this far to either side / forward or back of the centre (it
START_ANGLE_ERROR_DEG = 8.0             # must still fit: 5 cm / 4 cm is the limit), and this crooked
MOTOR_TAU_S = 0.03                      # motors reach ~63% of a new speed command after this long

# Centering (firmware, encoders only - no IMU): an observer estimates offset, heading error and
# the robot's own wheel-mismatch curve from the steering it commands + the side-wall distances
CENTER_KP = 1.2                         # rad/s of steering per cm off-centre (tuned for 381 rpm straights)
CENTER_KH = 14.0                        # rad/s of steering per rad of heading error
MAX_STEER_RAD_S = 2.0
OBS_K_OFFSET = 0.3                      # observer gains, applied per side-wall reading
OBS_K_HEADING = 0.02                    # rad per cm of reading error
OBS_K_CURVE = 0.0002                    # (rad/cm) per cm of reading error

# The match, as MMRC26 runs it (rule 6.1): one 8-minute window, the clock never stops.
# A run is timed from the front edge crossing the START line (leaving the start cell) to it
# crossing the FINISH line (the goal entrance), so the run-up and the stop inside the goal are free.
MATCH_TIME_S = 480.0
HANDLING_TIME_S = 8.0                   # picking the mouse up at the goal and setting it down at the start
AUTO_RESTART_S = 0.5                    # ... or, when it drove itself back, just the operator's go signal
AUTO_RETURN = False                     # True: it drives itself back to the start between runs
                                        # (False: the operator carries it back, costing HANDLING_TIME_S)
HOME_SPEED_CM_S = 45.0                  # the drive home is not timed, so take it easy: a crash there
                                        # costs a rescue and the next run, and gains nothing
RESCUE_TIME_S = 12.0                    # ... longer when it has crashed somewhere in the maze
START_BACKOFF_CM = 2.8                  # how far back in the start cell it lines up, for a flying start

# Simulation timing
PHYSICS_HZ = 200                        # physics / control loop rate
SIM_SPEEDS = [0.25, 0.5, 1, 2, 4, 8]    # playback multipliers (Up/Down arrows)
DEFAULT_SIM_SPEED = 1

# Movement helpers (shared by maze.py and micromouse.py)
DIRECTIONS = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
TARGET_CELLS = {(4, 4), (5, 4), (4, 5), (5, 5)}
START_CELL = (0, ROWS - 1)                  # bottom-left corner; its only opening is North (the next cell clockwise)
# rule 5.c: the start is in ONE of the four corners, walled on three sides; the opening faces the
# next cell clockwise around the maze (so it always opens with the maze on the mouse's right)
START_CORNERS = [((0, ROWS - 1), 'N'), ((0, 0), 'E'), ((COLS - 1, 0), 'S'), ((COLS - 1, ROWS - 1), 'W')]
RANDOM_START_CORNER = True                  # False: always the bottom-left corner
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