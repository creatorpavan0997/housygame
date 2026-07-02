from django.db import models
import uuid

class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PlayerProfile(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='profile')
    games_played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    total_points = models.PositiveIntegerField(default=0)

    @property
    def win_percentage(self):
        if self.games_played == 0:
            return 0.0
        return round((self.wins / self.games_played) * 100, 2)

    def __str__(self):
        return f"{self.player.name}'s Profile"

class Achievement(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='achievements')
    title = models.CharField(max_length=100)
    description = models.TextField()
    unlocked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.player.name} - {self.title}"

class DailyReward(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name='daily_reward')
    last_claimed = models.DateTimeField(null=True, blank=True)
    streak = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.player.name} - Streak: {self.streak}"
