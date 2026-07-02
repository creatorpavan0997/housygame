from django.shortcuts import render, redirect
from django.contrib import messages
from apps.accounts.models import Player, PlayerProfile
from apps.rooms.models import Room, RoomPlayer
import random
import string

def generate_room_id():
    while True:
        # Generates a random 6-digit Room ID
        room_id = ''.join(random.choices(string.digits, k=6))
        if not Room.objects.filter(room_id=room_id).exists():
            return room_id

def index_view(request):
    player_id = request.session.get('player_id')
    player_name = request.session.get('player_name')

    # If player is not set in session, show Welcome screen (enter name)
    if not player_id:
        return render(request, 'index.html', {'step': 'welcome'})
    
    # Check if player exists in DB
    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        request.session.flush()
        return render(request, 'index.html', {'step': 'welcome'})

    # Else show Home screen (Create or Join Game options)
    profile, _ = PlayerProfile.objects.get_or_create(player=player)
    return render(request, 'index.html', {
        'step': 'home',
        'player_name': player_name,
        'profile': profile
    })

def set_name_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, "Name cannot be empty.")
            return redirect('index')

        # Create or fetch Player object
        player = Player.objects.create(name=name[:50])
        PlayerProfile.objects.create(player=player)

        # Store in session
        request.session['player_id'] = str(player.id)
        request.session['player_name'] = player.name

        # If they had a pending room link to join, join it now
        pending_room_id = request.session.pop('redirect_room_id', None)
        if pending_room_id:
            return redirect('join_by_link', room_id=pending_room_id)

        return redirect('index')
    return redirect('index')

def create_room_view(request):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return redirect('index')

    if request.method == 'POST':
        room_id = generate_room_id()
        room = Room.objects.create(room_id=room_id, host=player, status='LOBBY')
        
        # Add host to RoomPlayer
        RoomPlayer.objects.create(room=room, player=player, is_host=True)

        return redirect('room_lobby', room_id=room_id)
    return redirect('index')

def join_room_view(request):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        return redirect('index')

    if request.method == 'POST':
        room_id = request.POST.get('room_id', '').strip()
        if not room_id:
            messages.error(request, "Room ID cannot be empty.")
            return redirect('index')

        try:
            room = Room.objects.get(room_id=room_id)
        except Room.DoesNotExist:
            messages.error(request, f"Room {room_id} does not exist.")
            return redirect('index')

        if room.status == 'FINISHED':
            messages.error(request, f"Room {room_id} has already finished.")
            return redirect('index')

        # Join the room in DB
        RoomPlayer.objects.get_or_create(room=room, player=player, defaults={'is_host': False})

        return redirect('room_lobby', room_id=room_id)
    return redirect('index')

def join_by_link_view(request, room_id):
    player_id = request.session.get('player_id')

    # If name not set, store room_id and prompt to set name
    if not player_id:
        request.session['redirect_room_id'] = room_id
        messages.info(request, "Please enter your name first to join the room.")
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        request.session.flush()
        request.session['redirect_room_id'] = room_id
        return redirect('index')

    try:
        room = Room.objects.get(room_id=room_id)
    except Room.DoesNotExist:
        messages.error(request, f"Room {room_id} does not exist.")
        return redirect('index')

    if room.status == 'FINISHED':
        messages.error(request, f"Room {room_id} has already finished.")
        return redirect('index')

    # Join room player
    RoomPlayer.objects.get_or_create(room=room, player=player, defaults={'is_host': False})
    return redirect('room_lobby', room_id=room_id)

def room_lobby_view(request, room_id):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
        room = Room.objects.get(room_id=room_id)
        # Verify player belongs to this room
        room_player = RoomPlayer.objects.get(room=room, player=player)
    except (Player.DoesNotExist, Room.DoesNotExist, RoomPlayer.DoesNotExist):
        messages.error(request, "Access Denied. You are not registered in this room.")
        return redirect('index')

    # If the game has already started, redirect straight to the game screen!
    if room.status == 'PLAYING':
        return redirect('play_game', room_id=room_id)

    # Build shareable link
    scheme = request.is_secure() and "https" or "http"
    host = request.get_host()
    join_link = f"{scheme}://{host}/join/{room_id}"

    context = {
        'room': room,
        'is_host': room_player.is_host,
        'player': player,
        'join_link': join_link,
    }
    return render(request, 'lobby.html', context)
