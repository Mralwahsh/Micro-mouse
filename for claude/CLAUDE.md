# Project Overview: IEEE Micromouse Simulator & Telemetry Dashboard

Act as an expert Python/C++ developer and Machine Learning engineer specializing in Reinforcement Learning and embedded robotics. 

I am building a Micromouse simulator. I have just refactored the codebase into a clean, multi-file Object-Oriented Programming (OOP) architecture. Currently, it uses discrete grid-based movement (DFS for exploration, BFS for shortest path optimization) across a 3-round search system. 

## Current Architecture
The project is split into 5 files:
1. `config.py`: Contains all constants, dimensions (10x10 IEEE standard), and Pygame colors.
2. `cell.py`: Defines the `Cell` class (tracks walls and visited status).
3. `maze.py`: Defines the `Maze` class (generates the IEEE layout and handles BFS pathfinding).
4. `micromouse.py`: Defines the `Micromouse` AI class (handles the 3-round memory states and DFS exploration logic).
5. `main.py`: The `DashboardApp` entry point that renders a 4-panel Pygame UI (Physical Map, Search Memory, Current Best Path, Absolute Shortest Path).

## Ultimate Goals & Next Steps
My goal is to eventually transition this logic into a continuous physics environment (F1 racing style with velocity, acceleration, and hitboxes), wrap it in a standard Gymnasium environment, and train an autonomous agent using Reinforcement Learning (e.g., Stable-Baselines3). Ultimately, the inference engine will be ported to C++ to run on an ESP32 microcontroller with physical sensors and motor drivers.

## Instructions for this session
Below is the current source code for all 5 files. Please review the architecture. 

[WAIT FOR MY NEXT INSTRUCTION BEFORE WRITING NEW CODE]