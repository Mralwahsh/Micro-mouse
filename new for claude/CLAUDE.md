# Project Overview: IEEE Micromouse Simulator & Telemetry Dashboard

Act as an expert Python/C++ developer and Machine Learning engineer specializing in Reinforcement Learning and embedded robotics. 

I am building a Micromouse simulator with a clean, multi-file Object-Oriented Programming (OOP) architecture. The mouse drives continuously (position in cm, heading angle, limited acceleration / speed, in-place turns), maps the maze only from noisy sensor distances, and navigates with flood fill (least-turn Dijkstra / BFS for path analysis) across a 3-round search system.

## Current Architecture
The project is split into 7 files:
1. `config.py`: All constants: 10x10 grid (kept on purpose), real-world sizes (18 cm cells, 1.2 cm walls, 8x10 cm mouse), the `SENSORS` layout (IR range 2.5 cm, TOF 80 cm), sensor rate / noise / dropout, mapping evidence thresholds, motion limits, physics rate, sim speeds, Pygame colors. `CELL_SIZE` is the only drawing-scale knob.
2. `cell.py`: Defines the `Cell` class (walls, `walls_known`, visited status).
3. `maze.py`: Defines the `Maze` class (generates the IEEE layout, BFS shortest path, least-turn Dijkstra).
4. `sensors.py`: `SensorArray.scan(px, py, theta)` casts each beam (numpy slab test) against real wall/post boxes and returns `Reading`s carrying ONLY a noisy distance (+ where the sensor is/points). No ground truth (which wall was hit) leaks out.
5. `mapper.py`: `Mapper` turns readings into per-edge evidence scores: beam end on a wall face = wall vote, beam passing a slot = open vote, driving through = certain open. Ambiguous hits (posts, corners) and one-sample dropouts are ignored. An edge is known at |score| >= `WALL_EVIDENCE_THRESHOLD`.
6. `micromouse.py`: The `Micromouse`: `update(physical_maze, dt)` per physics tick. Senses at `SENSOR_HZ`; always brakes towards a target cell centre and, near the braking point, decides: straight on through a confirmed-open edge (target extends, no stop) or stop at the centre and turn in place. Only ever drives through confirmed-open edges. Rounds restart by hand-placing at the start.
7. `main.py`: The `DashboardApp` Pygame UI: "The Maze" (ground truth), "Running Maze" (the mouse's map, sensor hit point cloud, live beams), right sidebar with on/off overlay buttons + run stats + sensor readings, blue Regenerate / Start buttons at the bottom. Up/Down arrows change sim speed (x0.25 - x8).

Validation used so far: headless runs over 200 random mazes -> 0 collisions, 0 wrongly-mapped edges, 0 failed rounds.

## Sensor layout (from the user's hardware sketch)
2 side IR distance sensors pointing straight left/right; 3 TOF at the rear: one centre pointing forward, two at the rear corners angled 45° across the body (beams cross at the centre). Defined in `config.SENSORS`. With 2.5 cm range the side IR never reaches a wall while the mouse is centred (wall face is ~4.9 cm away); the diagonal TOFs are what map the side walls.

## Ultimate Goals & Next Steps
My goal is to eventually transition this logic into a continuous physics environment (F1 racing style with velocity, acceleration, and hitboxes), wrap it in a standard Gymnasium environment, and train an autonomous agent using Reinforcement Learning (e.g., Stable-Baselines3). Ultimately, the inference engine will be ported to C++ to run on an ESP32 microcontroller with physical sensors and motor drivers.

## Instructions
[WAIT FOR MY NEXT INSTRUCTION BEFORE WRITING NEW CODE]