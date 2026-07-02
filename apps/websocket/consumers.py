import json
import asyncio
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from apps.accounts.models import Player, PlayerProfile
from apps.rooms.models import Room, RoomPlayer
from apps.game.models import Game, Ticket, CalledNumber, Claim, Winner
from apps.game.engine import generate_rabbithouse_ticket, validate_claim
from apps.leaderboard.models import GameHistory, Statistics

# Global dictionary to track running game tasks
# Key: room_id, Value: asyncio.Task
game_tasks = {}

class RabbitHouseConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        self.player_id = self.scope['session'].get('player_id')

        if not self.player_id:
            await self.close()
            return

        # Fetch player and room
        self.player = await self.get_player(self.player_id)
        self.room = await self.get_room(self.room_id)

        if not self.player or not self.room:
            await self.close()
            return

        # Accept connection
        await self.accept()

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # Set player status to online in database
        await self.set_player_online_status(self.room, self.player, True)

        # Broadcast update to group
        await self.broadcast_player_list()

        # If game is already playing, send current game state to the reconnected player
        await self.sync_reconnected_player()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Set player status to offline in database
            await self.set_player_online_status(self.room, self.player, False)

            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            # Broadcast update
            await self.broadcast_player_list()

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'start_game':
            await self.handle_start_game()
        elif action == 'draw_number':
            await self.handle_draw_number()
        elif action == 'pause_game':
            await self.handle_pause_game()
        elif action == 'resume_game':
            await self.handle_resume_game()
        elif action == 'claim_prize':
            pattern = data.get('pattern')
            await self.handle_claim_prize(pattern)
        elif action == 'remove_player':
            target_player_id = data.get('player_id')
            await self.handle_remove_player(target_player_id)

    # --- ACTION HANDLERS ---

    async def handle_start_game(self):
        # Only Host can start the game
        is_host = await self.check_is_host()
        if not is_host:
            return

        # Check player counts (min 2, max 7 for this logic, but we can bypass min for development/testing if needed)
        player_count = await self.get_active_players_count()
        if player_count < 2:
            await self.send(json.dumps({
                'type': 'error',
                'message': 'Cannot start game. Need at least 2 players.'
            }))
            return

        # Start game in DB, generate tickets
        game, tickets = await self.start_game_db()

        # Broadcast game started to everyone (without tickets in the broad payload)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_started_broadcast',
                'game_id': game.id
            }
        )

        # Trigger background drawing loop if auto mode
        if game.draw_mode == 'AUTO':
            self.start_background_game_loop(self.room_id)

    async def handle_draw_number(self):
        is_host = await self.check_is_host()
        if not is_host:
            return
        
        game = await self.get_active_game()
        if not game or game.draw_mode != 'MANUAL' or game.is_paused:
            return

        drawn = await self.draw_next_number(game)
        if drawn:
            await self.broadcast_number_drawn(drawn['number'], drawn['history'])
        else:
            await self.end_game_flow()

    async def handle_pause_game(self):
        is_host = await self.check_is_host()
        if not is_host:
            return
        await self.set_game_pause_status(True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_status_update',
                'is_paused': True,
                'message': 'Game paused by host'
            }
        )

    async def handle_resume_game(self):
        is_host = await self.check_is_host()
        if not is_host:
            return
        await self.set_game_pause_status(False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_status_update',
                'is_paused': False,
                'message': 'Game resumed by host'
            }
        )

    async def handle_claim_prize(self, pattern):
        game = await self.get_active_game()
        if not game or game.is_paused:
            return

        result = await self.process_claim(game, self.player, pattern)

        # Broadcast claim results
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'claim_broadcast',
                'player_name': self.player.name,
                'player_id': str(self.player.id),
                'pattern': pattern,
                'is_valid': result['is_valid'],
                'message': result['message'],
                'leaderboard': result['leaderboard']
            }
        )

        # If claim is Full House and is valid, end the game!
        if pattern == 'full_house' and result['is_valid']:
            await self.end_game_flow()

    async def handle_remove_player(self, player_id):
        is_host = await self.check_is_host()
        if not is_host:
            return

        # Cannot remove host
        if str(player_id) == str(self.player_id):
            return

        removed = await self.remove_player_db(player_id)
        if removed:
            # Force close the removed player's socket connection by sending group message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_removed_broadcast',
                    'player_id': str(player_id)
                }
            )
            await self.broadcast_player_list()

    # --- BROADCAST GROUP MESSAGE RECIPIENTS ---

    async def game_started_broadcast(self, event):
        # Each client requests their individual ticket
        ticket = await self.get_player_ticket(event['game_id'])
        await self.send(json.dumps({
            'type': 'game_started',
            'game_id': event['game_id'],
            'ticket': ticket
        }))

    async def game_status_update(self, event):
        await self.send(json.dumps({
            'type': 'game_status',
            'is_paused': event['is_paused'],
            'message': event['message']
        }))

    async def claim_broadcast(self, event):
        await self.send(json.dumps({
            'type': 'claim_result',
            'player_name': event['player_name'],
            'player_id': event['player_id'],
            'pattern': event['pattern'],
            'status': 'APPROVED' if event['is_valid'] else 'REJECTED',
            'message': event['message'],
            'leaderboard': event['leaderboard']
        }))

    async def player_removed_broadcast(self, event):
        if str(self.player_id) == event['player_id']:
            await self.send(json.dumps({
                'type': 'removed',
                'message': 'You have been removed by the host.'
            }))
            await self.close()

    async def number_drawn_broadcast(self, event):
        await self.send(json.dumps({
            'type': 'number_drawn',
            'number': event['number'],
            'timer': event['timer'],
            'history': event['history']
        }))

    async def game_over_broadcast(self, event):
        await self.send(json.dumps({
            'type': 'game_over',
            'winners': event['winners'],
            'final_leaderboard': event['final_leaderboard']
        }))

    async def player_list_broadcast(self, event):
        await self.send(json.dumps({
            'type': 'player_list',
            'players': event['players']
        }))

    # --- UTILITY HELPERS ---

    async def broadcast_player_list(self):
        players = await self.get_room_players()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_list_broadcast',
                'players': players
            }
        )

    async def broadcast_number_drawn(self, number, history):
        game = await self.get_active_game()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'number_drawn_broadcast',
                'number': number,
                'timer': game.timer_seconds if game else 6,
                'history': history
            }
        )

    async def end_game_flow(self):
        # Cancel any background task running
        self.stop_background_game_loop(self.room_id)

        results = await self.finish_game_db()
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_over_broadcast',
                'winners': results['winners'],
                'final_leaderboard': results['leaderboard']
            }
        )

    async def sync_reconnected_player(self):
        state = await self.get_game_state_sync()
        if state:
            await self.send(json.dumps({
                'type': 'sync_state',
                'game_status': state['status'],
                'ticket': state['ticket'],
                'called_history': state['called_history'],
                'last_number': state['last_number'],
                'is_paused': state['is_paused'],
                'leaderboard': state['leaderboard']
            }))

    # --- BACKGROUND LOOP HANDLING ---

    def start_background_game_loop(self, room_id):
        # Cancel existing task if any
        self.stop_background_game_loop(room_id)
        
        task = asyncio.create_task(self.auto_draw_loop(room_id))
        game_tasks[room_id] = task

    def stop_background_game_loop(self, room_id):
        task = game_tasks.pop(room_id, None)
        if task:
            task.cancel()

    async def auto_draw_loop(self, room_id):
        try:
            # Wait short time before drawing first number
            await asyncio.sleep(2)
            
            while True:
                game = await self.get_active_game()
                if not game:
                    break

                if game.is_paused:
                    await asyncio.sleep(1)
                    continue

                drawn = await self.draw_next_number(game)
                if not drawn:
                    # No numbers left, end game
                    break

                await self.broadcast_number_drawn(drawn['number'], drawn['history'])
                
                # Countdown sleep
                await asyncio.sleep(game.timer_seconds)

            # End the game if we exit loop naturally (all numbers called)
            await self.end_game_flow()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("Error in auto draw loop:", e)

    # --- DATABASE SYNC HELPERS (ORM interaction) ---

    @database_sync_to_async
    def get_player(self, player_id):
        try:
            return Player.objects.get(id=player_id)
        except Player.DoesNotExist:
            return None

    @database_sync_to_async
    def get_room(self, room_id):
        try:
            return Room.objects.get(room_id=room_id)
        except Room.DoesNotExist:
            return None

    @database_sync_to_async
    def get_room_players(self):
        players = RoomPlayer.objects.filter(room=self.room).select_related('player')
        return [
            {
                'id': str(rp.player.id),
                'name': rp.player.name,
                'is_online': rp.is_online,
                'is_host': rp.is_host
            } for rp in players
        ]

    @database_sync_to_async
    def set_player_online_status(self, room, player, is_online):
        RoomPlayer.objects.filter(room=room, player=player).update(is_online=is_online)

    @database_sync_to_async
    def check_is_host(self):
        return RoomPlayer.objects.filter(room=self.room, player=self.player, is_host=True).exists()

    @database_sync_to_async
    def get_active_players_count(self):
        return RoomPlayer.objects.filter(room=self.room, is_online=True).count()

    @database_sync_to_async
    def start_game_db(self):
        # Update room status
        self.room.status = 'PLAYING'
        self.room.save()

        # Create Game instance
        game, created = Game.objects.get_or_create(room=self.room, ended_at__isnull=True)
        
        # Generate tickets for all players in room
        room_players = RoomPlayer.objects.filter(room=self.room)
        for rp in room_players:
            # Create a unique ticket
            ticket_grid = generate_rabbithouse_ticket()
            Ticket.objects.get_or_create(game=game, player=rp.player, defaults={'grid': ticket_grid})

            # Update stats
            profile, _ = PlayerProfile.objects.get_or_create(player=rp.player)
            profile.games_played += 1
            profile.save()

            # Record GameHistory entry
            GameHistory.objects.get_or_create(
                player=rp.player,
                game_id=game.id,
                defaults={
                    'room_id': self.room.room_id,
                    'is_host': rp.is_host,
                    'points_earned': 0
                }
            )

        return game, list(game.tickets.all())

    @database_sync_to_async
    def get_player_ticket(self, game_id):
        try:
            ticket = Ticket.objects.get(game_id=game_id, player=self.player)
            return ticket.grid
        except Ticket.DoesNotExist:
            return []

    @database_sync_to_async
    def get_active_game(self):
        try:
            return Game.objects.get(room=self.room, ended_at__isnull=True)
        except Game.DoesNotExist:
            return None

    @database_sync_to_async
    def set_game_pause_status(self, is_paused):
        Game.objects.filter(room=self.room, ended_at__isnull=True).update(is_paused=is_paused)

    @database_sync_to_async
    def draw_next_number(self, game):
        # Fetch existing drawn numbers
        called = list(CalledNumber.objects.filter(game=game).values_list('number', flat=True))
        
        # All numbers called
        if len(called) >= 90:
            return None

        # Select a random number between 1 and 90 that is not in called list
        available = [n for n in range(1, 91) if n not in called]
        num = random.choice(available)

        # Save to database
        CalledNumber.objects.create(
            game=game,
            number=num,
            sequence=len(called) + 1
        )

        new_history = called + [num]
        return {
            'number': num,
            'history': new_history
        }

    @database_sync_to_async
    def process_claim(self, game, player, pattern):
        called = list(CalledNumber.objects.filter(game=game).values_list('number', flat=True))
        ticket = Ticket.objects.get(game=game, player=player)

        # Check if this pattern was already claimed and awarded to someone else in this game
        already_won = Winner.objects.filter(game=game, pattern_name=pattern).exists()
        if already_won:
            return {
                'is_valid': False,
                'message': f'{pattern.replace("_", " ").title()} has already been won by another player.',
                'leaderboard': self.get_leaderboard_data(game)
            }

        # Run validation logic from engine
        is_valid = validate_claim(ticket.grid, called, pattern)

        # Record the claim
        Claim.objects.create(game=game, player=player, pattern_name=pattern, is_valid=is_valid)

        # Define points
        points_map = {
            'early_five': 10,
            'top_line': 20,
            'middle_line': 20,
            'bottom_line': 20,
            'four_corners': 25,
            'full_house': 50,
        }
        points = points_map.get(pattern, 0)

        # Profile / History updates
        profile, _ = PlayerProfile.objects.get_or_create(player=player)
        history = GameHistory.objects.get(player=player, game_id=game.id)
        stats, _ = Statistics.objects.get_or_create(player=player)

        if is_valid:
            # Award points
            Winner.objects.create(game=game, player=player, pattern_name=pattern, points_awarded=points)
            
            profile.total_points += points
            if pattern == 'full_house':
                profile.wins += 1
            profile.save()

            history.points_earned += points
            history.save()

            # Stats update
            if pattern == 'early_five': stats.early_fives += 1
            elif pattern == 'top_line': stats.top_lines += 1
            elif pattern == 'middle_line': stats.middle_lines += 1
            elif pattern == 'bottom_line': stats.bottom_lines += 1
            elif pattern == 'four_corners': stats.four_corners += 1
            elif pattern == 'full_house': stats.full_houses += 1
            stats.save()

            msg = f'Claim APPROVED! {player.name} won {pattern.replace("_", " ").title()} (+{points} pts).'
        else:
            # Penalty: deduct 5 points (minimum 0 total)
            penalty = 5
            profile.total_points = max(0, profile.total_points - penalty)
            profile.save()

            history.points_earned = max(0, history.points_earned - penalty)
            history.save()

            msg = f'Claim REJECTED! {player.name} claimed an invalid {pattern.replace("_", " ").title()} (-5 pts penalty).'

        return {
            'is_valid': is_valid,
            'message': msg,
            'leaderboard': self.get_leaderboard_data(game)
        }

    def get_leaderboard_data(self, game):
        # Fetch leaderboard snapshot for this active game
        histories = GameHistory.objects.filter(game_id=game.id).select_related('player').order_by('-points_earned')
        return [
            {
                'player_name': h.player.name,
                'points': h.points_earned
            } for h in histories
        ]

    @database_sync_to_async
    def remove_player_db(self, player_id):
        try:
            rp = RoomPlayer.objects.get(room=self.room, player_id=player_id)
            rp.delete()
            return True
        except RoomPlayer.DoesNotExist:
            return False

    @database_sync_to_async
    def finish_game_db(self):
        # Update game end timestamp
        game = Game.objects.get(room=self.room, ended_at__isnull=True)
        game.ended_at = timezone.now()
        game.save()

        # Update room status
        self.room.status = 'FINISHED'
        self.room.save()

        # Gather final winners
        winners = list(Winner.objects.filter(game=game).select_related('player').values('player__name', 'pattern_name', 'points_awarded'))
        
        # Leaderboard
        leaderboard = self.get_leaderboard_data(game)

        return {
            'winners': winners,
            'leaderboard': leaderboard
        }

    @database_sync_to_async
    def get_game_state_sync(self):
        try:
            game = Game.objects.get(room=self.room, ended_at__isnull=True)
            called = list(CalledNumber.objects.filter(game=game).values_list('number', flat=True))
            ticket = Ticket.objects.get(game=game, player=self.player)
            leaderboard = self.get_leaderboard_data(game)
            
            return {
                'status': self.room.status,
                'ticket': ticket.grid,
                'called_history': called,
                'last_number': called[-1] if called else None,
                'is_paused': game.is_paused,
                'leaderboard': leaderboard
            }
        except (Game.DoesNotExist, Ticket.DoesNotExist):
            return None
