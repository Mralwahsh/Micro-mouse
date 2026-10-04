# main.py
import math
import pygame
import sys
from config import *
from maze import Maze
from match import Match, KINDS
from sensors import body_to_world

# ---- Two-panel layout (derived from config so the grid size can change) ----
PITCH = CELL_SIZE + WALL_THICKNESS           # distance between neighbouring cell origins
WORLD_PX = PITCH / CELL_SIZE_CM              # px per real cm for sensor beams and the mouse body
PANEL_TOP = 60
PANEL_1_X = PADDING                          # "The Maze"      (ground truth + overlays)
PANEL_2_X = PADDING * 2 + MAZE_PIXEL_WIDTH   # "Running Maze"  (what the mouse knows)

MAZES_CENTER_X = PANEL_1_X + (MAZE_PIXEL_WIDTH * 2 + PADDING) // 2

# Sidebar on the right of both mazes: overlay buttons, then run stats, then sensor readings
SIDEBAR_X = PADDING * 3 + MAZE_PIXEL_WIDTH * 2
SIDEBAR_W = 360
TOGGLE_COLS = 2
TOGGLE_H = 36
TOGGLE_GAP = 8
TOGGLES_Y = PANEL_TOP
TOGGLE_W = (SIDEBAR_W - TOGGLE_GAP * (TOGGLE_COLS - 1)) // TOGGLE_COLS

# (key, button label, overlay colour) - every overlay starts hidden
TOGGLES = [
    ("shortest",   "Shortest Path",   COLOR_SOLUTION),
    ("least_turn", "Least Turns",     COLOR_LEAST_TURN),
    ("mouse_best", "Mouse Best Path", (255, 200, 0)),
    ("explored",   "Explored Cells",  COLOR_VISITED_TRAIL),
    ("flood",      "Flood Values",    (200, 200, 200)),
    ("mouse",      "Mouse Position",  COLOR_PHYSICAL_MOUSE),
    ("rays",       "Sensor Rays",     (255, 110, 110)),
    ("trail",      "Speed Path",      (255, 200, 0)),
]
TOGGLES_ON_AT_START = {"mouse", "trail"}   # show the REAL robot and how it weaves by default
TOGGLE_ROWS = (len(TOGGLES) + TOGGLE_COLS - 1) // TOGGLE_COLS

STATS_Y = TOGGLES_Y + TOGGLE_ROWS * (TOGGLE_H + TOGGLE_GAP) + 14
CONTROLS_Y = PANEL_TOP + MAZE_PIXEL_HEIGHT + 20
APP_WIDTH = SIDEBAR_X + SIDEBAR_W + PADDING
APP_HEIGHT = CONTROLS_Y + 44 + 40

COLOR_GOAL = (60, 50, 0)
COLOR_TOGGLE_OFF = (70, 70, 70)
COLOR_MEMORY_WALL = (230, 230, 230)
COLOR_POST_DIM = (90, 90, 90)
COLOR_SENSOR = {"IR": (255, 190, 40), "TOF": (255, 110, 110)}


def speed_color(v):
    """Red (stopped) -> yellow (half speed) -> green (top speed)."""
    t = max(0.0, min(1.0, v / MAX_SPEED_CM_S))
    return (int(255 * min(1.0, 2 * (1 - t))), int(255 * min(1.0, 2 * t)), 0)


class DashboardApp:
    """Two panels: the true maze with switchable overlays, and the mouse's live run."""
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((APP_WIDTH, APP_HEIGHT))
        pygame.display.set_caption("IEEE Micromouse Simulator")
        self.font_bold = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 17)
        self.font_toggle = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_flood = pygame.font.SysFont("Arial", 15)
        self.font_btn = pygame.font.SysFont("Arial", 18, bold=True)
        self.clock = pygame.time.Clock()

        self.regen_btn = pygame.Rect(MAZES_CENTER_X - 190, CONTROLS_Y, 170, 44)
        self.explore_btn = pygame.Rect(MAZES_CENTER_X + 20, CONTROLS_Y, 170, 44)
        self.kind_btn = pygame.Rect(MAZES_CENTER_X + 230, CONTROLS_Y, 190, 44)
        self.match_kind = "MATCH"                      # "MATCH" (8 minutes) or "THREE_RUNS"

        self.speed_idx = SIM_SPEEDS.index(DEFAULT_SIM_SPEED)
        self.sim_accum = 0.0          # simulated seconds waiting to be stepped
        self.toggles = {key: key in TOGGLES_ON_AT_START for key, _, _ in TOGGLES}
        self.toggle_rects = {}
        for i, (key, _, _) in enumerate(TOGGLES):
            col, row = i % TOGGLE_COLS, i // TOGGLE_COLS
            self.toggle_rects[key] = pygame.Rect(SIDEBAR_X + col * (TOGGLE_W + TOGGLE_GAP),
                                                 TOGGLES_Y + row * (TOGGLE_H + TOGGLE_GAP),
                                                 TOGGLE_W, TOGGLE_H)

        self._initialize_simulation()

    def _initialize_simulation(self):
        self.physical_maze = Maze(is_blank_memory=False)
        self.match = Match(self.physical_maze, self.match_kind)
        self.mouse = self.match.mouse
        start = self.physical_maze.start
        self.absolute_shortest_path = self.physical_maze.get_shortest_path(*start)
        self.least_turn_path = self.physical_maze.get_least_turn_path(*start, self.physical_maze.start_opening)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def cell_rect(ox, oy, x, y):
        return pygame.Rect(ox + WALL_THICKNESS + x * PITCH, oy + WALL_THICKNESS + y * PITCH,
                           CELL_SIZE, CELL_SIZE)

    def draw_cell_walls(self, ox, oy, x, y, walls, color):
        r = self.cell_rect(ox, oy, x, y)
        if walls['N']: pygame.draw.rect(self.screen, color, (r.x, r.y - WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
        if walls['S']: pygame.draw.rect(self.screen, color, (r.x, r.bottom, CELL_SIZE, WALL_THICKNESS))
        if walls['W']: pygame.draw.rect(self.screen, color, (r.x - WALL_THICKNESS, r.y, WALL_THICKNESS, CELL_SIZE))
        if walls['E']: pygame.draw.rect(self.screen, color, (r.right, r.y, WALL_THICKNESS, CELL_SIZE))

    def draw_line_on_wall(self, ox, oy, key, color):
        """Paint a (missing) wall slot, e.g. the start / finish line, given its wall key."""
        kind, a, b = key
        if kind == 'H':
            rect = (ox + WALL_THICKNESS + a * PITCH, oy + b * PITCH, CELL_SIZE, WALL_THICKNESS)
        else:
            rect = (ox + a * PITCH, oy + WALL_THICKNESS + b * PITCH, WALL_THICKNESS, CELL_SIZE)
        pygame.draw.rect(self.screen, color, rect)

    def draw_posts(self, ox, oy, color):
        for i in range(COLS + 1):
            for j in range(ROWS + 1):
                if i == COLS // 2 and j == ROWS // 2:     # no post in the middle of the goal room
                    continue
                pygame.draw.rect(self.screen, color, (ox + i * PITCH, oy + j * PITCH, WALL_THICKNESS, WALL_THICKNESS))

    def draw_path(self, ox, oy, path, color, width):
        if not path or len(path) < 2:
            return
        points = [self.cell_rect(ox, oy, x, y).center for x, y in path]
        pygame.draw.lines(self.screen, color, False, points, width)

    @staticmethod
    def world_to_px(ox, oy, wx, wy):
        """Real-world cm (origin = centre of the top-left post) to screen pixels."""
        return (ox + WALL_THICKNESS / 2 + wx * WORLD_PX, oy + WALL_THICKNESS / 2 + wy * WORLD_PX)

    def draw_mouse(self, ox, oy, color, pose, readings=None):
        """Rectangular body at real scale (MOUSE_WIDTH_CM x MOUSE_LENGTH_CM) at pose (px, py, theta).
        With readings, also draws every sensor and its beam (dot = where the beam hit)."""
        px, py, theta = pose
        hw, hl = MOUSE_WIDTH_CM / 2, MOUSE_LENGTH_CM / 2
        corners = [body_to_world(px, py, theta, bx, by) for bx, by in ((-hw, hl), (hw, hl), (hw, -hl), (-hw, -hl))]
        body = [self.world_to_px(ox, oy, *c) for c in corners]
        pygame.draw.polygon(self.screen, color, body)
        pygame.draw.polygon(self.screen, (255, 255, 255), body, 1)

        # white arrow marks the front of the mouse
        arrow = [body_to_world(px, py, theta, bx, by) for bx, by in ((0, hl - 0.5), (-hw * 0.4, hl - 3.5), (hw * 0.4, hl - 3.5))]
        pygame.draw.polygon(self.screen, (255, 255, 255), [self.world_to_px(ox, oy, *p) for p in arrow])

        for r in readings or []:
            c = COLOR_SENSOR[r.sensor["kind"]]
            start = self.world_to_px(ox, oy, *r.origin)
            end = self.world_to_px(ox, oy, *r.end)
            pygame.draw.line(self.screen, c, start, end, 2)
            if r.distance is not None:
                pygame.draw.circle(self.screen, c, end, 5)
                pygame.draw.circle(self.screen, (255, 255, 255), end, 5, 1)
            pygame.draw.circle(self.screen, c, start, 3)

    def draw_title(self, text, ox):
        self.screen.blit(self.font_bold.render(text, True, (255, 255, 255)), (ox, PANEL_TOP - 30))

    def draw_text(self, text, x, y, color=COLOR_TEXT_METRIC):
        self.screen.blit(self.font_small.render(text, True, color), (x, y))

    # ----------------------------------------------------------------- panels
    def draw_the_maze(self, solution_path):
        """Panel 1: ground-truth maze plus whichever overlays are switched on."""
        ox, oy = PANEL_1_X, PANEL_TOP
        self.draw_title("The Maze", ox)
        self.screen.set_clip(pygame.Rect(ox, oy, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
        pygame.draw.rect(self.screen, COLOR_FOG, (ox, oy, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))

        for x in range(COLS):
            for y in range(ROWS):
                color = COLOR_FLOOR
                if (x, y) in TARGET_CELLS:
                    color = COLOR_GOAL
                if self.toggles["explored"] and (x, y) in self.mouse.global_visited:
                    color = COLOR_VISITED_TRAIL
                pygame.draw.rect(self.screen, color, self.cell_rect(ox, oy, x, y))
        pygame.draw.rect(self.screen, COLOR_START, self.cell_rect(ox, oy, *self.physical_maze.start))

        self.draw_posts(ox, oy, COLOR_WALL_RED)
        for x in range(COLS):
            for y in range(ROWS):
                self.draw_cell_walls(ox, oy, x, y, self.physical_maze.grid[x][y].walls, COLOR_WALL_RED)

        # official timing lines (rule 6.1.f): start = leaving the start cell, finish = goal entrance
        sx, sy = self.physical_maze.start
        self.draw_line_on_wall(ox, oy, Maze.edge_key(sx, sy, self.physical_maze.start_opening), (0, 230, 120))
        self.draw_line_on_wall(ox, oy, self.physical_maze.goal_entrance, (255, 200, 0))

        if self.toggles["flood"]:
            for x in range(COLS):
                for y in range(ROWS):
                    val = self.mouse.flood[x][y]
                    if val is not None:
                        surf = self.font_flood.render(str(val), True, (200, 200, 200))
                        self.screen.blit(surf, surf.get_rect(center=self.cell_rect(ox, oy, x, y).center))

        # least-turn drawn thickest underneath so overlapping paths all stay visible
        if self.toggles["least_turn"]:
            self.draw_path(ox, oy, self.least_turn_path, COLOR_LEAST_TURN, 7)
        if self.toggles["mouse_best"]:
            self.draw_path(ox, oy, solution_path, (255, 200, 0), 5)
        if self.toggles["shortest"]:
            self.draw_path(ox, oy, self.absolute_shortest_path, COLOR_SOLUTION, 3)
        m = self.mouse
        if self.toggles["trail"]:
            # the real path, coloured by speed: red = slow, yellow = half speed, green = top speed
            for (x1, y1, _), (x2, y2, v) in zip(m.true_trail, m.true_trail[1:]):
                pygame.draw.line(self.screen, speed_color(v), self.world_to_px(ox, oy, x1, y1),
                                 self.world_to_px(ox, oy, x2, y2), 3)
        crashed = m.run["crashed"]
        if self.toggles["mouse"] or self.toggles["rays"] or crashed:
            b = m.body                                            # where the robot REALLY is
            self.draw_mouse(ox, oy, (255, 60, 60) if crashed else COLOR_PHYSICAL_MOUSE, (b.px, b.py, b.theta),
                            m.readings if self.toggles["rays"] else None)
        self.screen.set_clip(None)

    def draw_running_maze(self):
        """Panel 2: only what the mouse has sensed, its trail this round, and the mouse itself."""
        ox, oy = PANEL_2_X, PANEL_TOP
        title = "Running Maze"
        if self.match.state != "READY":
            run = self.mouse.run
            what = "CRASH" if run["crashed"] else ("HOME RUN" if self.mouse.phase == "TO_START" else run["mode"])
            title += f"  (run {len(self.mouse.runs)} - {what})"
        self.draw_title(title, ox)
        self.screen.set_clip(pygame.Rect(ox, oy, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
        pygame.draw.rect(self.screen, (0, 0, 0), (ox, oy, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))

        for x in range(COLS):
            for y in range(ROWS):
                cell = self.mouse.memory.grid[x][y]
                color = COLOR_FOG
                if cell.discovered:
                    color = COLOR_FLOOR
                if (x, y) in self.mouse.round_visited:
                    color = COLOR_VISITED_TRAIL
                pygame.draw.rect(self.screen, color, self.cell_rect(ox, oy, x, y))

        self.draw_posts(ox, oy, COLOR_POST_DIM)
        for x in range(COLS):
            for y in range(ROWS):
                cell = self.mouse.memory.grid[x][y]
                known_walls = {d: cell.walls_known[d] and cell.walls[d] for d in DIRECTIONS}
                self.draw_cell_walls(ox, oy, x, y, known_walls, COLOR_MEMORY_WALL)

        # every recent sensor hit, as the mouse measured it: the raw material of its map
        for hx, hy in self.mouse.mapper.hits:
            pygame.draw.circle(self.screen, (255, 140, 140), self.world_to_px(ox, oy, hx, hy), 1)
        m = self.mouse                                            # where the robot BELIEVES it is
        self.draw_mouse(ox, oy, (255, 60, 60) if m.run["crashed"] else COLOR_MEMORY_MOUSE,
                        m.believed_pose(), m.believed_readings)
        self.screen.set_clip(None)

    def draw_toggles(self, mouse_pos):
        self.draw_title("Overlays", SIDEBAR_X)
        for key, label, color in TOGGLES:
            rect = self.toggle_rects[key]
            on = self.toggles[key]
            bg = COLOR_BUTTON if on else COLOR_TOGGLE_OFF
            if rect.collidepoint(mouse_pos):
                bg = COLOR_BUTTON_HOVER
            pygame.draw.rect(self.screen, bg, rect, border_radius=5)
            swatch = pygame.Rect(rect.x + 10, rect.centery - 7, 14, 14)
            pygame.draw.rect(self.screen, color, swatch, 0 if on else 2, border_radius=2)
            surf = self.font_toggle.render(label, True, (255, 255, 255) if on else (180, 180, 180))
            self.screen.blit(surf, surf.get_rect(midleft=(swatch.right + 8, rect.centery)))

    def draw_stats(self, solution_path):
        x, y, line = SIDEBAR_X, STATS_Y, 22
        m = self.mouse
        self.screen.blit(self.font_bold.render("Run Stats", True, (255, 255, 255)), (x, y))
        y += 30

        if solution_path:
            best = f"{len(solution_path) - 1} steps / {Maze.count_turns(solution_path)} turns"
        else:
            best = "not found yet"
        sp = len(self.absolute_shortest_path) - 1 if self.absolute_shortest_path else 0
        lt = len(self.least_turn_path) - 1 if self.least_turn_path else 0
        match = self.match
        crashes = sum(r["crashed"] for r in m.runs)
        best_time = f"{match.best_time:.2f} s" if match.best_time else "-"
        recent = "  ".join(f"{t:.2f}" for t in match.times[-4:]) or "-"
        state = match.state.title()
        if match.state == "HANDLING":
            back = "Restarting" if m.run["returned"] else "Carrying back"
            state = f"{back} ({match.handling_left:.1f} s)"
        if match.kind == "THREE_RUNS":
            state = {"READY": "press Start", "WAITING": "press Start for the next run",
                     "RUNNING": "running", "OVER": "all 3 runs done"}.get(match.state, state)
            per_run = [(f"{r['time']:.2f}s" if r["time"] is not None else "crash" if r["crashed"] else "-")
                       + f" {r['mode'][0]}" for r in m.runs]
            per_run += ["-"] * (3 - len(per_run))
            header = [
                (f"3 runs: run {max(1, len(m.runs))} of 3   {state}",
                 (255, 200, 0) if match.state == "OVER" else COLOR_TEXT_METRIC),
                ("Times: " + " | ".join(f"R{i + 1} {t}" for i, t in enumerate(per_run)), COLOR_TEXT_METRIC),
                (f"Best {best_time}   score {match.score:,.0f} (runs / best x 1000)", (120, 255, 120)),
            ]
        else:
            header = [
                (f"Match: {int(match.time_left) // 60}:{int(match.time_left) % 60:02d} left   {state}",
                 (255, 200, 0) if match.state == "OVER" else COLOR_TEXT_METRIC),
                (f"SCORE {match.score:,.0f}   = {len(match.times)} runs / {best_time} x 1000",
                 (120, 255, 120)),
                (f"Runs: {len(match.times)} scored, {crashes} crashed   best {best_time}", COLOR_TEXT_METRIC),
                (f"Last runs: {recent}", COLOR_TEXT_METRIC),
            ]
        rows = header + [
            (f"This run: {m.run['mode']}  {m.run_clock:.2f} s  {m.run['cells']} cells"
             + ("   driving home" if m.phase == "TO_START" else ""), COLOR_TEXT_METRIC),
            (f"Velocity: {abs(m.v):.0f} cm/s = {abs(m.v) * 60 / (math.pi * WHEEL_DIAMETER_CM):.0f} rpm "
             f"({m.motion.replace('_', ' ').lower()})", COLOR_TEXT_METRIC),
            (f"Off-centre: {m.true_offset():+.1f} cm (thinks {m.est_offset:+.1f})   heading: "
             f"{math.degrees((m.body.theta - m.theta + math.pi) % (2 * math.pi) - math.pi):+.1f}°",
             (255, 120, 120) if abs(m.true_offset()) > 2 else COLOR_TEXT_METRIC),
            (f"Motor speed: learned {m.speed_scale * 100:.1f} %  (real {sum(m.motor_gain) / 2 * 100:.1f} %)",
             COLOR_TEXT_METRIC),
            (f"Mouse best: {best}", (255, 200, 0)),
            (f"Shortest: {sp} steps / {Maze.count_turns(self.absolute_shortest_path, self.physical_maze.start_opening)} turns", COLOR_SOLUTION),
            (f"Least turns: {lt} steps / {Maze.count_turns(self.least_turn_path, self.physical_maze.start_opening)} turns", COLOR_LEAST_TURN),
            (f"Proven optimal: {'yes' if m.solved_optimally else 'no'}", COLOR_TEXT_METRIC),
            (f"Sim speed: x{SIM_SPEEDS[self.speed_idx]:g}  (Up / Down)", COLOR_TEXT_METRIC),
        ]
        for text, color in rows:
            self.draw_text(text, x, y, color)
            y += line

        y += 10
        self.screen.blit(self.font_bold.render("Sensors (cm)", True, (255, 255, 255)), (x, y))
        y += 30
        for r in self.mouse.readings:
            dist = f"{r.distance:.1f}" if r.distance is not None else "--"
            self.draw_text(f"{r.sensor['name']}: {dist}", x, y, COLOR_SENSOR[r.sensor["kind"]])
            y += line

    def draw_controls(self, mouse_pos):
        pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER if self.regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, self.regen_btn, border_radius=5)
        text_surf = self.font_btn.render("Regenerate", True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=self.regen_btn.center))

        pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER if self.explore_btn.collidepoint(mouse_pos) else COLOR_BUTTON, self.explore_btn, border_radius=5)
        n = len(self.mouse.runs)
        if self.match.kind == "THREE_RUNS":
            nxt = self.mouse.next_run_mode(last_chance=(n == 2)).title()
            btn_text = {"READY": "Start Run 1", "WAITING": f"Run {n + 1}: {nxt}", "RUNNING": f"Run {n}...",
                        "OVER": "3 runs done"}[self.match.state]
        else:
            btn_text = {"READY": "Start Match", "RUNNING": f"Run {n}...",
                        "HANDLING": "Carrying back...", "OVER": "Match over"}[self.match.state]
        text_surf = self.font_btn.render(btn_text, True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=self.explore_btn.center))

        # which kind of run-through: click to switch (restarts on the same maze)
        pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER if self.kind_btn.collidepoint(mouse_pos) else (90, 60, 160),
                         self.kind_btn, border_radius=5)
        text_surf = self.font_btn.render(f"Mode: {KINDS[self.match_kind]}", True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=self.kind_btn.center))

        if self.toggles["trail"]:                          # colour key for the speed path
            x0, y0, w = PANEL_1_X, CONTROLS_Y + 8, 150
            for i in range(w):
                pygame.draw.line(self.screen, speed_color(MAX_SPEED_CM_S * i / (w - 1)),
                                 (x0 + i, y0), (x0 + i, y0 + 10))
            self.screen.blit(self.font_toggle.render("slow", True, (200, 200, 200)), (x0, y0 + 14))
            fast = self.font_toggle.render(f"{MAX_SPEED_CM_S:.0f} cm/s", True, (200, 200, 200))
            self.screen.blit(fast, fast.get_rect(topright=(x0 + w, y0 + 14)))

        phys_cm = COLS * CELL_INSIDE_CM + (COLS + 1) * WALL_THICKNESS_CM
        dim_surf = self.font_small.render(f"Physical Dimensions: {phys_cm:.1f}cm x {phys_cm:.1f}cm", True, (180, 180, 180))
        self.screen.blit(dim_surf, dim_surf.get_rect(center=(MAZES_CENTER_X, APP_HEIGHT - 20)))

    # ------------------------------------------------------------------- loop
    def handle_click(self, pos):
        for key, rect in self.toggle_rects.items():
            if rect.collidepoint(pos):
                self.toggles[key] = not self.toggles[key]
                return
        if self.regen_btn.collidepoint(pos):
            self._initialize_simulation()
        elif self.explore_btn.collidepoint(pos):
            self.match.start()
        elif self.kind_btn.collidepoint(pos):
            self.match_kind = "THREE_RUNS" if self.match_kind == "MATCH" else "MATCH"
            self.match = Match(self.physical_maze, self.match_kind)     # same maze, fresh mouse
            self.mouse = self.match.mouse

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.speed_idx = min(len(SIM_SPEEDS) - 1, self.speed_idx + 1)
                    elif event.key == pygame.K_DOWN:
                        self.speed_idx = max(0, self.speed_idx - 1)

            # fixed-rate physics (PHYSICS_HZ), independent of the 60 fps render rate
            physics_dt = 1.0 / PHYSICS_HZ
            self.sim_accum = min(self.sim_accum + dt / 1000 * SIM_SPEEDS[self.speed_idx], 0.25)
            while self.sim_accum >= physics_dt:
                self.sim_accum -= physics_dt
                self.match.update(physics_dt)
            solution_path = self.mouse.memory.get_shortest_path(*self.physical_maze.start)

            mouse_pos = pygame.mouse.get_pos()
            self.screen.fill(COLOR_UI_BG)
            self.draw_the_maze(solution_path)
            self.draw_running_maze()
            self.draw_toggles(mouse_pos)
            self.draw_stats(solution_path)
            self.draw_controls(mouse_pos)

            pygame.display.flip()

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = DashboardApp()
    app.run()
