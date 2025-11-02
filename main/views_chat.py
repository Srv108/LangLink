import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.contrib.auth.models import User
from .models import ChatRoom, Message, Profile
from .forms import MessageForm

@login_required
def chat_room(request, room_name=None, user_id=None):
    """View for the chat room"""
    user = request.user
    
    # Get or create chat room
    if room_name:
        chat_room = get_object_or_404(ChatRoom, name=room_name, participants=user)
    elif user_id:
        other_user = get_object_or_404(User, id=user_id)
        chat_room = ChatRoom.objects.filter(participants=user).filter(participants=other_user).first()
        
        if not chat_room:
            # Create a new chat room
            chat_room = ChatRoom.objects.create(name=f"chat_{user.id}_{other_user.id}")
            chat_room.participants.add(user, other_user)
    else:
        # Get the most recent chat or redirect to matches
        chat_room = ChatRoom.objects.filter(participants=user).order_by('-last_updated').first()
        
    # Ensure we have a valid chat_room
    if not chat_room:
        return redirect('main:matches')  # or wherever you want to redirect if no chat exists
        if not chat_room:
            return redirect('matches')  # Redirect to matches if no chat exists
    
    # Get messages for the chat room
    messages = chat_room.messages.all().order_by('timestamp')
    
    # Mark messages as read
    chat_room.messages.filter(sender__in=chat_room.participants.exclude(id=user.id)).update(is_read=True)
    
    # Get other participant (for 1:1 chat)
    other_participant = chat_room.get_other_participant(user)
    
    # Get user's chat list
    chat_rooms = ChatRoom.objects.filter(participants=user).order_by('-last_updated')
    
    return render(request, 'chat/room.html', {
        'room_name': chat_room.name,
        'chat_room': chat_room,  # <-- THIS LINE IS ADDED
        'other_participant': other_participant,
        'chat_messages': messages,
        'chat_rooms': chat_rooms,
        'form': MessageForm(),
    })

@login_required
@require_http_methods(["POST"])
def send_message(request, room_name):
    """API endpoint to send a message"""
    chat_room = get_object_or_404(ChatRoom, name=room_name, participants=request.user)
    form = MessageForm(request.POST)
    
    if form.is_valid():
        message = Message.objects.create(
            room=chat_room,
            sender=request.user,
            content=form.cleaned_data['content']
        )
        
        # Update last_updated timestamp
        chat_room.save()
        
        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'sender': message.sender.username,
                'timestamp': message.timestamp.isoformat(),
                'is_read': message.is_read
            }
        })
    
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
def get_messages(request, room_name):
    """API endpoint to get messages for a chat room"""
    chat_room = get_object_or_404(ChatRoom, name=room_name, participants=request.user)
    messages = chat_room.messages.all().order_by('timestamp')
    
    # Mark messages as read
    chat_room.messages.filter(sender__in=chat_room.participants.exclude(id=request.user.id)).update(is_read=True)
    
    data = [{
        'id': msg.id,
        'content': msg.content,
        'sender': msg.sender.username,
        'timestamp': msg.timestamp.isoformat(),
        'is_read': msg.is_read,
        'is_own': msg.sender == request.user
    } for msg in messages]
    
    return JsonResponse({'messages': data})

@login_required
def get_unread_count(request):
    """API endpoint to get unread message count"""
    count = Message.objects.filter(
        room__participants=request.user,
        is_read=False
    ).exclude(sender=request.user).count()
    
    return JsonResponse({'unread_count': count})