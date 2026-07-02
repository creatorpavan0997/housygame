from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('claim-reward/', views.claim_daily_reward, name='claim_reward'),
]
