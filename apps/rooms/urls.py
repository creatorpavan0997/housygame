from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('set-name/', views.set_name_view, name='set_name'),
    path('create-room/', views.create_room_view, name='create_room'),
    path('join-room/', views.join_room_view, name='join_room'),
    path('join/<str:room_id>/', views.join_by_link_view, name='join_by_link'),
    path('room/<str:room_id>/', views.room_lobby_view, name='room_lobby'),
]
