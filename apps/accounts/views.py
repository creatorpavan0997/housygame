from django.shortcuts import render, redirect
from django.contrib import messages
from apps.accounts.models import Player, PlayerProfile, Achievement, DailyReward
from apps.leaderboard.models import GameHistory, Statistics
from django.utils import timezone

def profile_view(request):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
    except Player.DoesNotExist:
        request.session.flush()
        return redirect('index')

    profile, _ = PlayerProfile.objects.get_or_create(player=player)
    stats, _ = Statistics.objects.get_or_create(player=player)
    achievements = Achievement.objects.filter(player=player).order_by('-unlocked_at')
    history = GameHistory.objects.filter(player=player).order_by('-played_at')
    reward, _ = DailyReward.objects.get_or_create(player=player)

    # Simple Daily Reward claiming mechanism
    can_claim_reward = True
    if reward.last_claimed:
        now = timezone.now()
        time_diff = now - reward.last_claimed
        if time_diff.total_seconds() < 86400:  # Less than 24 hours
            can_claim_reward = False

    points_to_win = min((reward.streak + 1) * 5, 50)

    context = {
        'player': player,
        'profile': profile,
        'stats': stats,
        'achievements': achievements,
        'history': history,
        'reward': reward,
        'can_claim_reward': can_claim_reward,
        'points_to_win': points_to_win,
    }
    return render(request, 'profile.html', context)

def claim_daily_reward(request):
    player_id = request.session.get('player_id')
    if not player_id:
        return redirect('index')

    try:
        player = Player.objects.get(id=player_id)
        reward, _ = DailyReward.objects.get_or_create(player=player)
        
        now = timezone.now()
        if not reward.last_claimed or (now - reward.last_claimed).total_seconds() >= 86400:
            # If claimed within 48 hours, increment streak, else reset to 1
            if reward.last_claimed and (now - reward.last_claimed).total_seconds() < 172800:
                reward.streak += 1
            else:
                reward.streak = 1
                
            reward.last_claimed = now
            reward.save()

            # Award points for daily claim
            profile, _ = PlayerProfile.objects.get_or_create(player=player)
            points_won = min(reward.streak * 5, 50)  # capped at 50 pts
            profile.total_points += points_won
            profile.save()

            # Grant achievement if streak gets high
            if reward.streak >= 7:
                Achievement.objects.get_or_create(
                    player=player,
                    title="Loyal RabbitHouse Fan",
                    defaults={'description': "Claimed daily rewards for 7 consecutive days!"}
                )

            messages.success(request, f"Daily reward claimed! Streak: {reward.streak}. You received +{points_won} points!")
        else:
            messages.error(request, "Daily reward already claimed today.")
    except Player.DoesNotExist:
        pass

    return redirect('profile')
