# cell.py

class Cell:
    """Represents a single square in the maze."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.walls = {'N': True, 'S': True, 'E': True, 'W': True}
        self.visited = False
        self.discovered = False