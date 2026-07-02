from django.db import models
from apps.accounts.models import Player
from apps.game.models import Game

class GameHistory(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='game_histories')
    game_id = models.IntegerField()  # Loose coupling in case Game is deleted
    room_id = models.CharField(max_length=6)
    points_earned = models.IntegerField(default=0)
    is_host = models.BooleanField(default=False)
    played_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} played Game {self.game_id} in Room {self.room_id}"

class Statistics(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='statistics')
    early_fives = models.PositiveIntegerField(default=0)
    top_lines = models.PositiveIntegerField(default=0)
    middle_lines = models.PositiveIntegerField(default=0)
    bottom_lines = models.PositiveIntegerField(default=0)
    four_corners = models.PositiveIntegerField(default=0)
    full_houses = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Stats for {self.player.name}"
