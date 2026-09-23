# match.py
"""One MMRC26 match: an 8-minute window, runs back to back (rule 6.1).

The clock never stops - not between runs, not while the operator picks the mouse up at the
goal and sets it back down at the start. Every run that reaches the goal is scored:

    score = successful runs / best official run time * 1000     (rule 6.3)

so the number of runs counts as much as the fastest one.
"""
from config import MATCH_TIME_S, HANDLING_TIME_S, RESCUE_TIME_S, AUTO_RESTART_S
from micromouse import Micromouse


class Match:
    def __init__(self, physical_maze):
        self.maze = physical_maze
        self.mouse = Micromouse()
        self.clock = 0.0                        # seconds used of the match window
        self.state = "READY"                    # READY | RUNNING | HANDLING | OVER
        self.handling_left = 0.0

    # --------------------------------------------------------------- control
    def start(self):
        if self.state == "READY":
            self.state = "RUNNING"
            self.mouse.begin_run()

    def update(self, dt):
        if self.state in ("READY", "OVER"):
            return
        self.clock += dt
        if self.clock >= MATCH_TIME_S:
            self.clock = MATCH_TIME_S
            self.state = "OVER"
            self.mouse.state = "IDLE"
            return
        if self.state == "RUNNING":
            self.mouse.update(self.maze, dt)
            if self.mouse.state != "EXPLORING":            # the run ended: home, or crashed on the way
                run = self.mouse.run
                self.state = "HANDLING"
                self.handling_left = (AUTO_RESTART_S if run["returned"] else
                                      RESCUE_TIME_S if run["crashed"] else HANDLING_TIME_S)
        else:                                              # between runs (it drove home, or was carried)
            self.handling_left -= dt
            if self.handling_left <= 0:
                self.mouse.begin_run()
                self.state = "RUNNING"

    # --------------------------------------------------------------- scoring
    @property
    def times(self):
        return self.mouse.official_times()

    @property
    def best_time(self):
        return min(self.times) if self.times else None

    @property
    def score(self):
        return len(self.times) / self.best_time * 1000 if self.times else 0.0

    @property
    def time_left(self):
        return max(0.0, MATCH_TIME_S - self.clock)
