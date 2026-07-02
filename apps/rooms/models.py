from django.db import models
from apps.accounts.models import Player

class Room(models.Model):
    STATUS_CHOICES = [
        ('LOBBY', 'Lobby'),
        ('PLAYING', 'Playing'),
        ('FINISHED', 'Finished'),
    ]

    room_id = models.CharField(max_length=6, unique=True, db_index=True)
    host = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, related_name='hosted_rooms')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='LOBBY')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Room {self.room_id} ({self.status})"

class RoomPlayer(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='room_players')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='room_memberships')
    is_online = models.BooleanField(default=True)
    is_host = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'player')

    def __str__(self):
        return f"{self.player.name} in Room {self.room.room_id}"
