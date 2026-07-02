from django.test import TestCase
from apps.game.engine import generate_rabbithouse_ticket, validate_claim

class RabbitHouseEngineTestCase(TestCase):
    def test_ticket_generation_dimensions(self):
        ticket = generate_rabbithouse_ticket()
        self.assertEqual(len(ticket), 3, "Ticket should have 3 rows")
        for row in ticket:
            self.assertEqual(len(row), 9, "Each row should have 9 columns")

    def test_ticket_generation_counts(self):
        ticket = generate_rabbithouse_ticket()
        # Count numbers per row
        for i, row in enumerate(ticket):
            numbers_count = len([cell for cell in row if cell != 0])
            self.assertEqual(numbers_count, 5, f"Row {i} should contain exactly 5 numbers")

        # Total numbers on ticket must be 15
        all_numbers = [cell for row in ticket for cell in row if cell != 0]
        self.assertEqual(len(all_numbers), 15, "Ticket should contain exactly 15 numbers in total")

    def test_ticket_generation_ranges(self):
        ticket = generate_rabbithouse_ticket()
        ranges = [
            (1, 9),
            (10, 19),
            (20, 29),
            (30, 39),
            (40, 49),
            (50, 59),
            (60, 69),
            (70, 79),
            (80, 90)
        ]
        for row in ticket:
            for c, cell in enumerate(row):
                if cell != 0:
                    start, end = ranges[c]
                    self.assertTrue(start <= cell <= end, f"Cell value {cell} out of column {c} range ({start}-{end})")

    def test_ticket_generation_sorting_and_uniqueness(self):
        ticket = generate_rabbithouse_ticket()
        
        # Uniqueness
        all_numbers = [cell for row in ticket for cell in row if cell != 0]
        self.assertEqual(len(all_numbers), len(set(all_numbers)), "All numbers must be unique")

        # Sorting within columns
        for c in range(9):
            col_numbers = [ticket[r][c] for r in range(3) if ticket[r][c] != 0]
            self.assertEqual(col_numbers, sorted(col_numbers), f"Column {c} numbers must be sorted top to bottom")

    def test_claim_validation(self):
        # A mock ticket
        ticket = [
            [4, 0, 23, 0, 42, 0, 65, 71, 0],
            [0, 12, 28, 33, 0, 52, 0, 78, 0],
            [9, 0, 0, 39, 45, 59, 0, 0, 88]
        ]
        # Numbers: 4, 23, 42, 65, 71, 12, 28, 33, 52, 78, 9, 39, 45, 59, 88 (15 total)
        
        # 1. Early Five
        called = [4, 12, 23, 33, 42]
        self.assertTrue(validate_claim(ticket, called, 'early_five'))
        self.assertFalse(validate_claim(ticket, called[:4], 'early_five'))
        
        # 2. Top Line (4, 23, 42, 65, 71)
        self.assertTrue(validate_claim(ticket, [4, 23, 42, 65, 71, 99], 'top_line'))
        self.assertFalse(validate_claim(ticket, [4, 23, 42, 65], 'top_line'))

        # 3. Four Corners (first and last of top and bottom rows: 4, 71, 9, 88)
        self.assertTrue(validate_claim(ticket, [4, 71, 9, 88, 15], 'four_corners'))
        self.assertFalse(validate_claim(ticket, [4, 71, 9], 'four_corners'))

        # 4. Full House (all numbers called)
        all_nums = [4, 23, 42, 65, 71, 12, 28, 33, 52, 78, 9, 39, 45, 59, 88]
        self.assertTrue(validate_claim(ticket, all_nums, 'full_house'))
        self.assertFalse(validate_claim(ticket, all_nums[:-1], 'full_house'))
