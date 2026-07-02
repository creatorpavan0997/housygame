from django.shortcuts import render, redirect
from apps.accounts.models import Player
from apps.rooms.models import Room, RoomPlayer

def play_game_view(request, room_id):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
        room = Room.objects.get(room_id=room_id)
        room_player = RoomPlayer.objects.get(room=room, player=player)
    except (Player.DoesNotExist, Room.DoesNotExist, RoomPlayer.DoesNotExist):
        return redirect('index')

    # If status is still lobby, redirect back to lobby
    if room.status == 'LOBBY':
        return redirect('room_lobby', room_id=room_id)

    context = {
        'room': room,
        'player': player,
        'is_host': room_player.is_host,
    }
    return render(request, 'game.html', context)
