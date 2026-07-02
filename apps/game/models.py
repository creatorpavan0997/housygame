from django.db import models
from apps.accounts.models import Player
from apps.rooms.models import Room

class Game(models.Model):
    DRAW_MODE_CHOICES = [
        ('AUTO', 'Automatic'),
        ('MANUAL', 'Manual'),
    ]

    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='game')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    timer_seconds = models.PositiveIntegerField(default=6)
    draw_mode = models.CharField(max_length=10, choices=DRAW_MODE_CHOICES, default='AUTO')
    is_paused = models.BooleanField(default=False)

    def __str__(self):
        return f"Game for Room {self.room.room_id}"

class Ticket(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='tickets')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='tickets')
    grid = models.JSONField()  # 3x9 nested list, 0 represents blank space

    def __str__(self):
        return f"Ticket for {self.player.name} in Game {self.game.id}"

class CalledNumber(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='called_numbers')
    number = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField()
    called_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('game', 'number')
        ordering = ['sequence']

    def __str__(self):
        return f"Game {self.game.id} - #{self.sequence}: {self.number}"

class Claim(models.Model):
    PATTERN_CHOICES = [
        ('early_five', 'Early Five'),
        ('top_line', 'Top Line'),
        ('middle_line', 'Middle Line'),
        ('bottom_line', 'Bottom Line'),
        ('four_corners', 'Four Corners'),
        ('full_house', 'Full House'),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='claims')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='claims')
    pattern_name = models.CharField(max_length=20, choices=PATTERN_CHOICES)
    is_valid = models.BooleanField()
    claimed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Valid" if self.is_valid else "Invalid"
        return f"{self.player.name} claimed {self.pattern_name} - {status}"

class Winner(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='winners')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='wins')
    pattern_name = models.CharField(max_length=20)
    points_awarded = models.PositiveIntegerField()
    awarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} won {self.pattern_name} (+{self.points_awarded})"
