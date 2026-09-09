# main.py
import pygame
import sys
from config import *
from maze import Maze
from micromouse import Micromouse

class DashboardApp:
    """Manages the UI, rendering loop, and input handling."""
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("IEEE 4-Panel Telemetry Dashboard (OOP Multi-file)")
        self.font_bold = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 15)
        self.font_btn = pygame.font.SysFont("Arial", 18, bold=True)
        self.clock = pygame.time.Clock()
        
        self.regen_btn = pygame.Rect(WINDOW_WIDTH // 2 - 160, WINDOW_HEIGHT - 70, 140, 40)
        self.explore_btn = pygame.Rect(WINDOW_WIDTH // 2 + 20, WINDOW_HEIGHT - 70, 140, 40)
        
        self._initialize_simulation()

    def _initialize_simulation(self):
        self.physical_maze = Maze(is_blank_memory=False)
        self.mouse = Micromouse()
        self.absolute_shortest_path = self.physical_maze.get_shortest_path(0, 9)

    def draw_maze_panel(self, offset_x, offset_y, title_text, maze_obj, is_memory=False, show_trail=False, path_to_draw=None, wall_color=COLOR_WALL_RED):
        title_surf = self.font_bold.render(title_text, True, (255, 255, 255))
        self.screen.blit(title_surf, (offset_x, offset_y - 25))
        
        if not is_memory:
            pygame.draw.rect(self.screen, COLOR_FOG, (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            start_px = offset_x + WALL_THICKNESS
            start_py = offset_y + WALL_THICKNESS + (9 * (CELL_SIZE + WALL_THICKNESS))
            pygame.draw.rect(self.screen, COLOR_START, (start_px, start_py, CELL_SIZE, CELL_SIZE))

            for i in range(COLS + 1):
                for j in range(ROWS + 1):
                    if i == 5 and j == 5: continue
                    px = offset_x + i * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + j * (CELL_SIZE + WALL_THICKNESS)
                    pygame.draw.rect(self.screen, wall_color, (px, py, WALL_THICKNESS, WALL_THICKNESS))

            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_obj.grid[x][y]
                    px = offset_x + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    pygame.draw.rect(self.screen, COLOR_FLOOR, (px + WALL_THICKNESS, py + WALL_THICKNESS, CELL_SIZE, CELL_SIZE))
                    
                    if cell.walls['N']: pygame.draw.rect(self.screen, wall_color, (px + WALL_THICKNESS, py, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['S']: pygame.draw.rect(self.screen, wall_color, (px + WALL_THICKNESS, py + CELL_SIZE + WALL_THICKNESS, CELL_SIZE, WALL_THICKNESS))
                    if cell.walls['W']: pygame.draw.rect(self.screen, wall_color, (px, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
                    if cell.walls['E']: pygame.draw.rect(self.screen, wall_color, (px + CELL_SIZE + WALL_THICKNESS, py + WALL_THICKNESS, WALL_THICKNESS, CELL_SIZE))
        
        else:
            pygame.draw.rect(self.screen, (0, 0, 0), (offset_x, offset_y, MAZE_PIXEL_WIDTH, MAZE_PIXEL_HEIGHT))
            
            for x in range(COLS):
                for y in range(ROWS):
                    cell = maze_obj.grid[x][y]
                    px = offset_x + WALL_THICKNESS + x * (CELL_SIZE + WALL_THICKNESS)
                    py = offset_y + WALL_THICKNESS + y * (CELL_SIZE + WALL_THICKNESS)
                    
                    if cell.discovered:
                        if show_trail and (x, y) in self.mouse.round_visited:
                            pygame.draw.rect(self.screen, COLOR_VISITED_TRAIL, (px, py, CELL_SIZE, CELL_SIZE))
                        
                        if cell.walls['N']: pygame.draw.line(self.screen, (255,255,255), (px, py), (px+CELL_SIZE, py), 1)
                        if cell.walls['S']: pygame.draw.line(self.screen, (255,255,255), (px, py+CELL_SIZE), (px+CELL_SIZE, py+CELL_SIZE), 1)
                        if cell.walls['W']: pygame.draw.line(self.screen, (255,255,255), (px, py), (px, py+CELL_SIZE), 1)
                        if cell.walls['E']: pygame.draw.line(self.screen, (255,255,255), (px+CELL_SIZE, py), (px+CELL_SIZE, py+CELL_SIZE), 1)

        if path_to_draw:
            for i in range(len(path_to_draw) - 1):
                x1, y1 = path_to_draw[i]
                x2, y2 = path_to_draw[i+1]
                start_px = offset_x + WALL_THICKNESS + (x1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                start_py = offset_y + WALL_THICKNESS + (y1 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_px = offset_x + WALL_THICKNESS + (x2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                end_py = offset_y + WALL_THICKNESS + (y2 * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
                pygame.draw.line(self.screen, COLOR_SOLUTION, (start_px, start_py), (end_px, end_py), 3)

    def draw_centered_text(self, text, center_x, y, color=COLOR_TEXT_METRIC):
        surf = self.font_small.render(text, True, color)
        rect = surf.get_rect(center=(center_x, y))
        self.screen.blit(surf, rect)

    def draw_mouse_tokens(self, offset_1, offset_2):
        if self.mouse.state in ["EXPLORING", "ROUND_PAUSED"]:
            m_px = offset_1 + WALL_THICKNESS + (self.mouse.x * (CELL_SIZE + WALL_THICKNESS)) + 2
            m_py = 50 + WALL_THICKNESS + (self.mouse.y * (CELL_SIZE + WALL_THICKNESS)) + 2
            pygame.draw.rect(self.screen, COLOR_PHYSICAL_MOUSE, (m_px, m_py, CELL_SIZE - 4, CELL_SIZE - 4), border_radius=3)

            c_x = offset_2 + WALL_THICKNESS + (self.mouse.x * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
            c_y = 50 + WALL_THICKNESS + (self.mouse.y * (CELL_SIZE + WALL_THICKNESS)) + CELL_SIZE // 2
            pygame.draw.circle(self.screen, COLOR_MEMORY_MOUSE, (c_x, c_y), CELL_SIZE // 3)

    def draw_ui(self):
        mouse_pos = pygame.mouse.get_pos()
        
        pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER if self.regen_btn.collidepoint(mouse_pos) else COLOR_BUTTON, self.regen_btn, border_radius=5)
        text_surf = self.font_btn.render("Regenerate", True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=self.regen_btn.center))

        pygame.draw.rect(self.screen, COLOR_BUTTON_HOVER if self.explore_btn.collidepoint(mouse_pos) else COLOR_BUTTON, self.explore_btn, border_radius=5)
        
        btn_text = "Start Round 1"
        if self.mouse.state == "EXPLORING": btn_text = f"Running R{self.mouse.current_round}..."
        elif self.mouse.state == "ROUND_PAUSED": btn_text = f"Start Round {self.mouse.current_round + 1}"
        elif self.mouse.state == "DONE": btn_text = "Analysis Complete"
            
        text_surf = self.font_btn.render(btn_text, True, (255, 255, 255))
        self.screen.blit(text_surf, text_surf.get_rect(center=self.explore_btn.center))

        dim_string = "Physical Dimensions: 190.8cm x 190.8cm"
        dim_surf = self.font_small.render(dim_string, True, (180, 180, 180))
        self.screen.blit(dim_surf, dim_surf.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 20)))

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.regen_btn.collidepoint(event.pos):
                        self._initialize_simulation()
                        
                    elif self.explore_btn.collidepoint(event.pos):
                        if self.mouse.state == "IDLE":
                            self.mouse.state = "EXPLORING"
                        elif self.mouse.state == "ROUND_PAUSED":
                            self.mouse.start_next_round()

            self.mouse.update_logic(self.physical_maze)
            
            solution_path = []
            if self.mouse.state in ["EXPLORING", "ROUND_PAUSED", "DONE"]:
                solution_path = self.mouse.memory.get_shortest_path(0, 9)

            self.screen.fill(COLOR_UI_BG)

            offset_1 = PADDING
            offset_2 = offset_1 + MAZE_PIXEL_WIDTH + PADDING
            offset_3 = offset_2 + MAZE_PIXEL_WIDTH + PADDING
            offset_4 = offset_3 + MAZE_PIXEL_WIDTH + PADDING
            
            center_1 = PADDING + (MAZE_PIXEL_WIDTH // 2)
            center_2 = PADDING*2 + MAZE_PIXEL_WIDTH + (MAZE_PIXEL_WIDTH // 2)
            center_3 = PADDING*3 + MAZE_PIXEL_WIDTH*2 + (MAZE_PIXEL_WIDTH // 2)
            center_4 = PADDING*4 + MAZE_PIXEL_WIDTH*3 + (MAZE_PIXEL_WIDTH // 2)
            text_y_pos = 50 + MAZE_PIXEL_HEIGHT + 15

            self.draw_maze_panel(offset_1, 50, "Physical Map", self.physical_maze, is_memory=False)
            self.draw_centered_text(f"Round 1 Steps: {self.mouse.round_steps[0]}", center_1, text_y_pos)
            
            r_title = f"Search Memory (Round {self.mouse.current_round}/{self.mouse.max_rounds})" if self.mouse.state != "IDLE" else "Search Memory"
            self.draw_maze_panel(offset_2, 50, r_title, self.mouse.memory, is_memory=True, show_trail=True)
            self.draw_centered_text(f"Round 2 Steps: {self.mouse.round_steps[1]}", center_2, text_y_pos)

            self.draw_maze_panel(offset_3, 50, "Current Best Path", self.mouse.memory, is_memory=True, path_to_draw=solution_path)
            self.draw_centered_text(f"Round 3 Steps: {self.mouse.round_steps[2]}", center_3, text_y_pos)

            self.draw_maze_panel(offset_4, 50, "Absolute Shortest Path", self.physical_maze, is_memory=False, path_to_draw=self.absolute_shortest_path, wall_color=COLOR_WALL_BLUE)
            perfect_len = len(self.absolute_shortest_path) if self.absolute_shortest_path else 0
            self.draw_centered_text(f"Absolute Shortest Path: {perfect_len} steps", center_4, text_y_pos)

            self.draw_mouse_tokens(offset_1, offset_2)
            self.draw_ui()

            pygame.display.flip()
            self.clock.tick(30) 

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = DashboardApp()
    app.run()