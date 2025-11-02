from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views
from .views_chat import chat_room, send_message, get_messages, get_unread_count

app_name = 'main'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Matches and Messaging
    path('matches/', views.matches_view, name='matches'),
    
    # Chat URLs
    path('chat/', chat_room, name='chat_home'),
    path('chat/<str:room_name>/', chat_room, name='chat_room'),
    path('chat/user/<int:user_id>/', chat_room, name='chat_with_user'),
    path('api/chat/<str:room_name>/send/', send_message, name='send_message'),
    path('api/chat/<str:room_name>/messages/', get_messages, name='get_messages'),
    path('api/chat/unread-count/', get_unread_count, name='unread_count'),
    path('inbox/', views.inbox_view, name='inbox'),
    path('chat/<int:user_id>/', views.chat_view, name='chat'),
    
    # Progress Dashboard
    path('progress/', login_required(views.ProgressDashboardView.as_view()), name='progress_dashboard'),
    path('progress/add/', login_required(views.ProgressLogCreateView.as_view()), name='progress_add'),
    path('progress/<int:pk>/edit/', login_required(views.ProgressLogUpdateView.as_view()), name='progress_edit'),
    path('progress/<int:pk>/delete/', login_required(views.ProgressLogDeleteView.as_view()), name='progress_delete'),
    
    # Home/Index (redirect to profile if logged in, else login)
    path('', lambda request: views.matches_view(request) if request.user.is_authenticated else views.login_view(request), name='home'),
]
