from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.rooms.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('game/', include('apps.game.urls')),
]
