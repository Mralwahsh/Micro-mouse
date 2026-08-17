import random

def generate_maze(width, height):
    # 1. Initialize grid with walls (1 = wall, 0 = path)
    # The grid size must be odd to allow for walls between paths
    grid_w = width * 2 + 1
    grid_h = height * 2 + 1
    maze = [[1] * grid_w for _ in range(grid_h)]
    
    # 2. Track visited cells
    visited = set()
    
    def carve_path(cx, cy):
        visited.add((cx, cy))
        maze[cy * 2 + 1][cx * 2 + 1] = 0
        
        # Define 4 directions: (dx, dy)
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        random.shuffle(directions)
        
        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            
            # Check if neighbor is within bounds and unvisited
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                # Remove wall between current cell and neighbor
                maze[cy * 2 + 1 + dy][cx * 2 + 1 + dx] = 0
                # Recursively visit the neighbor
                carve_path(nx, ny)

    # Start carving from the top-left cell (0, 0)
    carve_path(0, 0)
    
    # Create an entrance (top-left) and exit (bottom-right)
    maze[1][0] = 0
    maze[grid_h - 2][grid_w - 1] = 0
    
    return maze

def print_maze(maze):
    for row in maze:
        # Render walls as blocks (█) and paths as empty spaces
        print("".join("██" if cell == 1 else "  " for cell in row))

# Change dimensions here (Width x Height of the underlying grid cells)
if __name__ == "__main__":
    width, height = 15, 10
    generated_maze = generate_maze(width, height)
    print_maze(generated_maze)