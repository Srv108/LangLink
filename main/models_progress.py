from django.db import models
from django.conf import settings
from django.utils import timezone

class LanguageProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='language_progress')
    language = models.CharField(max_length=100)
    level = models.CharField(max_length=50, choices=[
        ('beginner', 'Beginner'),
        ('elementary', 'Elementary'),
        ('intermediate', 'Intermediate'),
        ('upper_intermediate', 'Upper Intermediate'),
        ('advanced', 'Advanced'),
        ('native', 'Native')
    ])
    proficiency = models.PositiveIntegerField(default=0, help_text="Proficiency percentage (0-100)")
    hours_practiced = models.FloatField(default=0)
    words_learned = models.PositiveIntegerField(default=0)
    last_practiced = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Language Progress"
        unique_together = ('user', 'language')
    
    def __str__(self):
        return f"{self.user.username}'s {self.language} progress ({self.level})"

class PracticeSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='practice_sessions')
    language = models.CharField(max_length=100)
    session_type = models.CharField(max_length=50, choices=[
        ('chat', 'Chat'),
        ('voice', 'Voice Call'),
        ('video', 'Video Call'),
        ('other', 'Other')
    ])
    duration_minutes = models.PositiveIntegerField(help_text="Duration in minutes")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        # Update the related LanguageProgress when a session is saved
        super().save(*args, **kwargs)
        progress, created = LanguageProgress.objects.get_or_create(
            user=self.user,
            language=self.language,
            defaults={
                'level': 'beginner',
                'proficiency': 10,
                'hours_practiced': self.duration_minutes / 60
            }
        )
        if not created:
            progress.hours_practiced += self.duration_minutes / 60
            # Simple progression logic (1% per hour of practice, capped at 100%)
            progress.proficiency = min(progress.proficiency + (self.duration_minutes / 60), 100)
            progress.save()
    
    def __str__(self):
        return f"{self.user.username}'s {self.session_type} session - {self.duration_minutes}min"
