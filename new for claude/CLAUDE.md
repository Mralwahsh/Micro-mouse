# Project Overview: IEEE Micromouse Simulator & Telemetry Dashboard

Act as an expert Python/C++ developer and Machine Learning engineer specializing in Reinforcement Learning and embedded robotics. 

I am building a Micromouse simulator with a clean, multi-file Object-Oriented Programming (OOP) architecture. The mouse drives continuously (position in cm, heading angle, limited acceleration / speed, in-place turns), maps the maze only from noisy sensor distances, and navigates with flood fill (least-turn Dijkstra / BFS for path analysis) across a 3-round search system.

## Current Architecture
The project is split into 8 files (the 7 below plus `body.py`, the simulated physical robot - see "Drift & centering"):
1. `config.py`: All constants: 10x10 grid (kept on purpose), real-world sizes (18 cm cells, 1.2 cm walls, 8x10 cm mouse), the `SENSORS` layout (IR range 2.5 cm, TOF 80 cm), sensor rate / noise / dropout, mapping evidence thresholds, motion limits, physics rate, sim speeds, Pygame colors. `CELL_SIZE` is the only drawing-scale knob.
2. `cell.py`: Defines the `Cell` class (walls, `walls_known`, visited status).
3. `maze.py`: Defines the `Maze` class (generates the IEEE layout, BFS shortest path, least-turn Dijkstra).
4. `sensors.py`: `SensorArray.scan(px, py, theta)` casts each beam (numpy slab test) against real wall/post boxes and returns `Reading`s carrying ONLY a noisy distance (+ where the sensor is/points). No ground truth (which wall was hit) leaks out.
5. `mapper.py`: `Mapper` turns readings into per-edge evidence scores: beam end on a wall face = wall vote, beam passing a slot = open vote, driving through = certain open. Ambiguous hits (posts, corners) and one-sample dropouts are ignored. An edge is known at |score| >= `WALL_EVIDENCE_THRESHOLD`.
6. `micromouse.py`: The `Micromouse`: `update(physical_maze, dt)` per physics tick. Senses at `SENSOR_HZ`; always brakes towards a target cell centre and, near the braking point, decides: straight on through a confirmed-open edge (target extends, no stop) or stop at the centre and turn in place. Only ever drives through confirmed-open edges. Rounds restart by hand-placing at the start.
7. `main.py`: The `DashboardApp` Pygame UI: "The Maze" (ground truth), "Running Maze" (the mouse's map, sensor hit point cloud, live beams), right sidebar with on/off overlay buttons + run stats + sensor readings, blue Regenerate / Start buttons at the bottom. Up/Down arrows change sim speed (x0.25 - x8).

Validation used so far: headless runs over 200 random mazes -> 0 collisions, 0 wrongly-mapped edges, 0 failed rounds.

## Drive train & strategy
Two wheels on the body's centre line (turns on the spot), 34 mm wheels, motors 381 rpm at the wheel -> top speed ≈ 67.8 cm/s. Encoders on each motor (user confirmed). Accel 200 cm/s² and wheel track 7 cm are assumptions (in `config.py`); turn-rate limits are derived from the wheel limits. Rounds: SEARCH (flood fill at 40 cm/s) until the map proves the best route, then FAST (Dijkstra quickest route over confirmed-open edges, cost = cell time + turn time, full speed; re-plans if the map changes under it). The last round is always FAST. Keep the bot logic small and C++/ESP32-portable (user request).

## Drift & centering (reality gap)
The user's mouse has wheel encoders but NO IMU. `body.py` is the TRUE robot (simulation only): motor lag (`MOTOR_TAU_S` 30 ms), per-robot wheel-diameter mismatch (`WHEEL_MISMATCH`), wheel slip, hand-placement error, TOF readings that describe the pose `SENSOR_LATENCY_S` (20 ms) ago. `body.step()` returns what the ENCODERS measured; the firmware (`micromouse.py`) builds its believed pose only from those (`_odometry`) and places each reading at its believed pose 20 ms ago (`pose_hist`). Centering: an observer estimates offset, heading error and the robot's own wheel-mismatch curve from encoder turn + side-wall readings (z = offset + y_hit * heading) and steers on the estimates, so it keeps going straight in open stretches too. Diagonal TOF readings are only used where the map has a known wall (near a post: walls on BOTH sides) and the wall across the lane can't catch the beam first; the 2.5 cm IR is always used (it can only see something right beside the body). Turns are profiled on encoder angle, then wait for the wheels to settle; the over/undershoot becomes heading error. Front-wall re-centring (averaged front TOF) at every stop / after every turn. Any body point inside a wall/post = crash (round lost). Mapper only trusts readings up to `MAP_RANGE_CM` = 45 cm.
Measured (headless, 100 mazes / 300 runs, no IMU): ≈12% of runs crash, 0.73 cm RMS off-centre; most crashes in the first search. Gain sweeps barely move it: the limit is heading observability in open stretches (this maze generator is quite open) and the 2.5 cm IR range. An earlier gyro version (no motor lag) reached ≈2%.
Dashboard: The Maze shows the REAL body + its path (cyan, "Real Path"), red on crash; Running Maze shows the BELIEVED pose (incl. observer estimates).

## Sensor layout (from the user's hardware sketch)
2 side IR distance sensors pointing straight left/right; 3 TOF at the rear: one centre pointing forward, two at the rear corners angled 45° across the body (beams cross at the centre). Defined in `config.SENSORS`. With 2.5 cm range the side IR never reaches a wall while the mouse is centred (wall face is ~4.9 cm away); the diagonal TOFs are what map the side walls.

## Ultimate Goals & Next Steps
My goal is to eventually transition this logic into a continuous physics environment (F1 racing style with velocity, acceleration, and hitboxes), wrap it in a standard Gymnasium environment, and train an autonomous agent using Reinforcement Learning (e.g., Stable-Baselines3). Ultimately, the inference engine will be ported to C++ to run on an ESP32 microcontroller with physical sensors and motor drivers.

## Instructions
[WAIT FOR MY NEXT INSTRUCTION BEFORE WRITING NEW CODE]