from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Count, Sum
from .models import Profile, Message, ChatRoom, ProgressLog
from .forms import ProfileForm

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any context data you want to pass to the template
        context['features'] = [
            {
                'icon': 'bi-people',
                'title': 'Connect with Native Speakers',
                'description': 'Practice languages with native speakers from around the world.'
            },
            {
                'icon': 'bi-chat-square-text',
                'title': 'Real Conversations',
                'description': 'Engage in meaningful conversations and improve your language skills.'
            },
            {
                'icon': 'bi-globe',
                'title': 'Learn Anywhere',
                'description': 'Access our platform from any device, anywhere, anytime.'
            },
            {
                'icon': 'bi-award',
                'title': 'Earn Badges',
                'description': 'Get recognized for your language learning progress.'
            }
        ]
        return context

def register_view(request):
    if request.user.is_authenticated:
        return redirect('main:profile')
        
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('main:profile')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('main:profile')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('main:profile')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been logged out.')
    return redirect('login')  # Using the URL name from the project's urls.py

@login_required
def profile_view(request):
    profile = request.user.profile
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('main:profile')
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'profile.html', {'form': form})

@login_required
def matches_view(request):
    potential_matches = request.user.profile.get_potential_matches()
    return render(request, 'matches.html', {'matches': potential_matches})

@login_required
def chat_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    
    # Ensure users can only chat with their matches
    if not request.user.profile.get_potential_matches().filter(user=other_user).exists():
        messages.error(request, 'You can only chat with your language exchange partners.')
        return redirect('main:matches')
    
    # Get or create chat room for these users
    room = ChatRoom.get_or_create_for_users(request.user, other_user)
    
    # Get messages for this room
    chat_messages = room.messages.select_related('sender').order_by('timestamp')
    
    # Mark messages as read
    room.messages.filter(sender=other_user, is_read=False).update(is_read=True)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            # Create the message
            message = Message.objects.create(
                room=room,
                sender=request.user,
                content=content
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'status': 'success',
                    'message': 'Message sent successfully.',
                    'message_id': message.id,
                    'timestamp': message.timestamp.isoformat()
                })
    
    context = {
        'other_user': other_user,
        'messages': chat_messages,
        'room': room,
        'room_id': room.id,  # Make sure to pass room_id to the template
        'room_name': room.name  # Also pass room_name for WebSocket connection
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.template.loader import render_to_string
        messages_html = render_to_string('chat/messages_partial.html', context, request=request)
        return JsonResponse({
            'status': 'success',
            'messages_html': messages_html
        })
    
    return render(request, 'chat/room.html', context)
    
@login_required
def inbox_view(request):
    # Get all chat rooms where the current user is a participant
    chat_rooms = ChatRoom.objects.filter(participants=request.user)
    
    # Get the latest message for each chat room
    latest_messages = {}
    for room in chat_rooms:
        latest_message = Message.objects.filter(room=room).order_by('-timestamp').first()
        if latest_message:
            latest_messages[room.id] = {
                'content': latest_message.content,
                'timestamp': latest_message.timestamp,
                'sender': latest_message.sender,
                'is_read': latest_message.is_read
            }
    
    # Get unread message counts for each room
    unread_counts = {}
    for room in chat_rooms:
        unread_count = Message.objects.filter(
            room=room, 
            is_read=False
        ).exclude(sender=request.user).count()
        unread_counts[room.id] = unread_count
    
    # Prepare conversations data with the other user's information
    conversations = []
    for room in chat_rooms:
        # Get the other user in the chat (not the current user)
        other_user = room.participants.exclude(id=request.user.id).first()
        if other_user:  # Only include if we found another user
            conversations.append({
                'user': other_user,
                'room': room,
                'last_message': latest_messages.get(room.id, {})
            })
    
    context = {
        'conversations': conversations,
        'unread_counts': unread_counts,
    }
    return render(request, 'inbox.html', context)


class ProgressDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'progress/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get weekly summary
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        
        # Get logs from the past week
        weekly_logs = ProgressLog.objects.filter(
            user=user,
            date__range=[week_ago, today]
        )
        
        # Calculate weekly stats
        total_minutes = weekly_logs.aggregate(total=Sum('minutes_studied'))['total'] or 0
        total_words = weekly_logs.aggregate(total=Sum('words_learned'))['total'] or 0
        
        # Activity distribution
        activity_distribution = weekly_logs.values('activity_type').annotate(
            count=Count('id'),
            total_minutes=Sum('minutes_studied')
        )
        
        # Calculate percentages for activity distribution
        total_activities = sum(item['count'] for item in activity_distribution) if activity_distribution else 1
        for activity in activity_distribution:
            activity['percentage'] = (activity['count'] / total_activities * 100) if total_activities > 0 else 0
        
        # Get recent activities
        recent_activities = ProgressLog.objects.filter(user=user).order_by('-date')[:5]
        
        # Language distribution
        language_distribution = weekly_logs.values('language').annotate(
            total_minutes=Sum('minutes_studied')
        ).order_by('-total_minutes')
        
        # Calculate percentages for language distribution
        total_lang_minutes = sum(item['total_minutes'] for item in language_distribution) if language_distribution else 1
        for lang in language_distribution:
            lang['percentage'] = (lang['total_minutes'] / total_lang_minutes * 100) if total_lang_minutes > 0 else 0
            lang['color'] = self.get_language_color(lang['language'])
        
        # Calculate total hours studied
        total_hours = ProgressLog.objects.filter(user=user).aggregate(
            total=Sum('minutes_studied')
        )['total'] or 0
        
        # Add data to context
        context.update({
            'weekly_summary': {
                'total_minutes': total_minutes,
                'total_hours': round(total_minutes / 60, 1) if total_minutes else 0,
                'words_learned': total_words,
                'activity_distribution': activity_distribution,
                'percentage_complete': min(100, int((total_minutes / 300) * 100)) if total_minutes else 0,  # 5 hour weekly goal
                'goal': 300,  # 5 hours in minutes
                'total_days': (today - week_ago).days + 1
            },
            'recent_activities': recent_activities,
            'language_distribution': language_distribution,
            'total_hours_studied': round(total_hours / 60, 1) if total_hours else 0,
            'total_words_learned': ProgressLog.objects.filter(user=user).aggregate(
                total=Sum('words_learned')
            )['total'] or 0,
        })
        
        return context
    
    def get_language_color(self, language_code):
        """Return a consistent color for each language"""
        colors = {
            'en': '#3498db',  # English - Blue
            'es': '#e74c3c',  # Spanish - Red
            'fr': '#2ecc71',  # French - Green
            'de': '#f39c12',  # German - Orange
            'it': '#9b59b6',  # Italian - Purple
            'pt': '#1abc9c',  # Portuguese - Turquoise
            'ru': '#e67e22',  # Russian - Carrot
            'zh': '#e74c3c',  # Chinese - Red
            'ja': '#2c3e50',  # Japanese - Dark Blue
            'ko': '#34495e',  # Korean - Dark Gray
        }
        return colors.get(language_code, '#95a5a6')  # Default gray


class ProgressLogCreateView(LoginRequiredMixin, CreateView):
    model = ProgressLog
    fields = ['activity_type', 'language', 'minutes_studied', 'words_learned', 'proficiency_level', 'notes']
    template_name = 'progress/progress_form.html'
    success_url = reverse_lazy('main:progress_dashboard')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class ProgressLogUpdateView(LoginRequiredMixin, UpdateView):
    model = ProgressLog
    fields = ['activity_type', 'language', 'minutes_studied', 'words_learned', 'proficiency_level', 'notes']
    template_name = 'progress/progress_form.html'
    success_url = reverse_lazy('main:progress_dashboard')
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class ProgressLogDeleteView(LoginRequiredMixin, DeleteView):
    model = ProgressLog
    template_name = 'progress/progress_confirm_delete.html'
    success_url = reverse_lazy('main:progress_dashboard')
    
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)
