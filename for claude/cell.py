# cell.py

class Cell:
    """Represents a single square in the maze."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.walls = {'N': True, 'S': True, 'E': True, 'W': True}
        # walls_known[d] is True once a sensor reading has confirmed whether
        # edge d is open or closed. Used by the mouse to tell "wall here" apart
        # from "not explored yet" (the physical maze ignores this field).
        self.walls_known = {'N': False, 'S': False, 'E': False, 'W': False}
        self.visited = False
        self.discovered = False
