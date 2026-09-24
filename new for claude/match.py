# match.py
"""How the mouse's runs are played out. Two kinds:

  MATCH       One MMRC26 match (rule 6.1): an 8-minute window, runs back to back. The clock
              never stops - not between runs, not while the operator carries the mouse from the
              goal back to the start. Every run that reaches the goal is scored:
                  score = successful runs / best official run time * 1000     (rule 6.3)
  THREE_RUNS  Three chances from the start to the goal, each started by hand (button). The
              last one always races the best route the mouse has confirmed.
"""
from config import MATCH_TIME_S, HANDLING_TIME_S, RESCUE_TIME_S, AUTO_RESTART_S
from micromouse import Micromouse

KINDS = {"MATCH": "8-min match", "THREE_RUNS": "3 runs"}


class Match:
    def __init__(self, physical_maze, kind="MATCH"):
        self.maze = physical_maze
        self.kind = kind
        self.max_runs = 3 if kind == "THREE_RUNS" else None
        self.mouse = Micromouse()
        self.clock = 0.0                        # seconds used of the match window
        self.state = "READY"                    # READY | RUNNING | HANDLING | WAITING | OVER
        self.handling_left = 0.0

    # --------------------------------------------------------------- control
    def start(self):
        """The start button: begin the match / the next of the three runs."""
        if self.state in ("READY", "WAITING"):
            self._begin_run()

    def _begin_run(self):
        last_chance = self.max_runs is not None and len(self.mouse.runs) == self.max_runs - 1
        self.mouse.begin_run(last_chance=last_chance)
        self.state = "RUNNING"

    def update(self, dt):
        if self.state in ("READY", "WAITING", "OVER"):
            return
        if self.kind == "MATCH":
            self.clock += dt
            if self.clock >= MATCH_TIME_S:
                self.clock = MATCH_TIME_S
                self.state = "OVER"
                self.mouse.state = "IDLE"
                return
        if self.state == "RUNNING":
            self.mouse.update(self.maze, dt)
            if self.mouse.state != "EXPLORING":            # the run ended: at the goal, or crashed
                self._run_ended()
        else:                                              # HANDLING: carried back to the start
            self.handling_left -= dt
            if self.handling_left <= 0:
                self._begin_run()

    def _run_ended(self):
        if self.kind == "THREE_RUNS":
            self.state = "OVER" if len(self.mouse.runs) >= self.max_runs else "WAITING"
            return
        run = self.mouse.run
        self.state = "HANDLING"
        self.handling_left = (AUTO_RESTART_S if run["returned"] else
                              RESCUE_TIME_S if run["crashed"] else HANDLING_TIME_S)

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
