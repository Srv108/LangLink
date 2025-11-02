from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from django.views.generic import TemplateView
from .models import Profile, Message, ChatRoom
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
    chat_rooms = ChatRoom.objects.filter(participants=request.user).order_by('-last_updated')
    
    conversations = []
    for room in chat_rooms:
        # Get the other participant (for 1:1 chat)
        other_participant = room.get_other_participant(request.user)
        if not other_participant:  # Skip if no other participant (shouldn't happen)
            continue
            
        # Get the last message in this chat room
        last_message = room.messages.order_by('-timestamp').first()
        
        # Count unread messages
        unread_count = room.messages.filter(
            sender=other_participant,
            is_read=False
        ).count()
        
        conversations.append({
            'user': other_participant,
            'room': room,
            'last_message': last_message,
            'unread_count': unread_count,
            'is_sender': last_message and last_message.sender == request.user if last_message else False,
            'last_updated': room.last_updated
        })
    
    # Sort conversations by last_updated
    conversations.sort(key=lambda x: x['last_updated'] if x['last_updated'] else None, reverse=True)
    
    return render(request, 'inbox.html', {'conversations': conversations})
