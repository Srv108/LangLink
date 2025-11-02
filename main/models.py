import os
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def user_profile_picture_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'profile_pics/user_{instance.user.id}/{filename}'

class ChatRoom(models.Model):
    """Chat room for private messaging"""
    name = models.CharField(max_length=255, unique=True)
    participants = models.ManyToManyField(User, related_name='chat_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        usernames = [user.username for user in self.participants.all()]
        return f"Chat {self.id}: {', '.join(usernames)}" if usernames else f"Chat {self.id}: No participants"

    def get_other_participant(self, user):
        """Get the other participant in a 1:1 chat"""
        return self.participants.exclude(id=user.id).first()
        
    @classmethod
    def get_or_create_for_users(cls, user1, user2):
        """Get or create a chat room for two users"""
        # Create a unique room name by sorting user IDs to ensure consistency
        user_ids = sorted([str(user1.id), str(user2.id)])
        room_name = f"chat_{'_'.join(user_ids)}"
        
        # Try to get existing room with these participants
        room = cls.objects.filter(
            name=room_name,
            participants=user1
        ).filter(
            participants=user2
        ).first()
        
        # If room doesn't exist, create it
        if not room:
            room = cls.objects.create(name=room_name)
            room.participants.add(user1, user2)
            
        return room


class Profile(models.Model):
    """User profile with language preferences and additional info"""
    LANGUAGES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('zh', 'Chinese'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('hi', 'Hindi'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    native_language = models.CharField(max_length=2, choices=LANGUAGES)
    learning_language = models.CharField(max_length=2, choices=LANGUAGES)
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to=user_profile_picture_path, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_potential_matches(self):
        """Find users who want to learn your native language and speak your target language"""
        return Profile.objects.filter(
            native_language=self.learning_language,
            learning_language=self.native_language
        ).exclude(user=self.user)


class Message(models.Model):
    """Messages between users"""
    # New field for room-based messaging
    room = models.ForeignKey('ChatRoom', related_name='messages', null=True, blank=True, on_delete=models.CASCADE)
    
    # Original fields (keeping for backward compatibility during migration)
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', null=True, blank=True, on_delete=models.SET_NULL)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
        
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            return True
        return False


class ProgressLog(models.Model):
    """Track user's learning progress"""
    ACTIVITY_CHOICES = [
        ('chat', 'Chat'),
        ('lesson', 'Lesson'),
        ('practice', 'Speaking Practice'),
        ('vocab', 'Vocabulary'),
        ('grammar', 'Grammar'),
        ('other', 'Other')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress_logs')
    date = models.DateField(auto_now_add=True)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, default='chat')
    language = models.CharField(max_length=2, choices=Profile.LANGUAGES, default='en')
    minutes_studied = models.PositiveIntegerField(default=0)
    words_learned = models.PositiveIntegerField(default=0)
    proficiency_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('elementary', 'Elementary'),
        ('intermediate', 'Intermediate'),
        ('upper_intermediate', 'Upper Intermediate'),
        ('advanced', 'Advanced'),
        ('fluent', 'Fluent')
    ], default='beginner')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Progress Logs'

    def __str__(self):
        return f"{self.user.username}'s {self.get_activity_type_display()} on {self.date}"
    
    @classmethod
    def get_weekly_summary(cls, user):
        """Get weekly summary of user's progress"""
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        
        logs = cls.objects.filter(
            user=user,
            date__range=[week_ago, today]
        )
        
        total_minutes = sum(log.minutes_studied for log in logs)
        total_words = sum(log.words_learned for log in logs)
        
        return {
            'total_minutes': total_minutes,
            'total_hours': round(total_minutes / 60, 1),
            'words_learned': total_words,
            'activity_distribution': logs.values('activity_type').annotate(
                count=models.Count('id'),
                total_minutes=models.Sum('minutes_studied')
            )
        }


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile when a new user signs up"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=Message)
def send_message_notification(sender, instance, created, **kwargs):
    """Send WebSocket notification for new messages"""
    if created:
        channel_layer = get_channel_layer()
        room_name = f"chat_{instance.room.id}"
        
        # Notify all participants in the room
        for participant in instance.room.participants.all():
            if participant != instance.sender:  # Don't notify the sender
                async_to_sync(channel_layer.group_send)(
                    f"user_{participant.id}",
                    {
                        'type': 'chat_message',
                        'message': {
                            'room_id': instance.room.id,
                            'sender': instance.sender.username,
                            'content': instance.content,
                            'timestamp': instance.timestamp.isoformat(),
                            'is_read': instance.is_read
                        }
                    }
                )
