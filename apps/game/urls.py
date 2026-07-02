from django.urls import path
from . import views

urlpatterns = [
    path('<str:room_id>/', views.play_game_view, name='play_game'),
]
