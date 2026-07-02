import random

def get_ticket_mask():
    """
    Generates a 3x9 binary grid (mask) representing the structure of a RabbitHouse ticket.
    Each row must contain exactly 5 numbers (1s) and 4 blanks (0s).
    Each column must contain at least 1 number.
    """
    while True:
        grid = [[0]*9 for _ in range(3)]
        # Place 5 ones randomly in each row
        for r in range(3):
            cols = random.sample(range(9), 5)
            for c in cols:
                grid[r][c] = 1
        
        # Check column sums. Every column must have at least 1 number.
        col_sums = [sum(grid[r][c] for r in range(3)) for c in range(9)]
        if all(s >= 1 for s in col_sums):
            return grid

def generate_rabbithouse_ticket() -> list:
    """
    Generates a complete, valid RabbitHouse ticket grid (3x9 list of lists).
    0 represents a blank space.
    """
    mask = get_ticket_mask()
    ticket = [[0]*9 for _ in range(3)]
    
    # Columns contain numbers in specific ranges
    ranges = [
        (1, 9),      # Column 1
        (10, 19),    # Column 2
        (20, 29),    # Column 3
        (30, 39),    # Column 4
        (40, 49),    # Column 5
        (50, 59),    # Column 6
        (60, 69),    # Column 7
        (70, 79),    # Column 8
        (80, 90)     # Column 9
    ]
    
    for c in range(9):
        # Count numbers needed in this column
        k = sum(mask[r][c] for r in range(3))
        start, end = ranges[c]
        # Choose k unique numbers from column range and sort them
        nums = sorted(random.sample(range(start, end + 1), k))
        
        idx = 0
        for r in range(3):
            if mask[r][c] == 1:
                ticket[r][c] = nums[idx]
                idx += 1
                
    return ticket

def validate_claim(ticket_grid: list, called_numbers: list, pattern_name: str) -> bool:
    """
    Validates a player's claim pattern on the server side.
    """
    called_set = set(called_numbers)
    
    # Extract all numbers on the ticket (excluding blanks)
    all_ticket_numbers = [num for row in ticket_grid for num in row if num != 0]
    
    if pattern_name == 'early_five':
        # Any 5 numbers on the ticket have been called
        marked_numbers = [num for num in all_ticket_numbers if num in called_set]
        return len(marked_numbers) >= 5
        
    elif pattern_name == 'top_line':
        # All numbers on row 0 must be called
        row_numbers = [num for num in ticket_grid[0] if num != 0]
        return all(num in called_set for num in row_numbers)
        
    elif pattern_name == 'middle_line':
        # All numbers on row 1 must be called
        row_numbers = [num for num in ticket_grid[1] if num != 0]
        return all(num in called_set for num in row_numbers)
        
    elif pattern_name == 'bottom_line':
        # All numbers on row 2 must be called
        row_numbers = [num for num in ticket_grid[2] if num != 0]
        return all(num in called_set for num in row_numbers)
        
    elif pattern_name == 'four_corners':
        # First and last numbers of the top (row 0) and bottom (row 2) rows
        top_numbers = [num for num in ticket_grid[0] if num != 0]
        bottom_numbers = [num for num in ticket_grid[2] if num != 0]
        
        if not top_numbers or not bottom_numbers:
            return False
            
        corners = [top_numbers[0], top_numbers[-1], bottom_numbers[0], bottom_numbers[-1]]
        return all(num in called_set for num in corners)
        
    elif pattern_name == 'full_house':
        # All 15 numbers on the ticket must be called
        return all(num in called_set for num in all_ticket_numbers)
        
    return False
