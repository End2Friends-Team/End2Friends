from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from PIL import Image


# Represents a user account, the thing that logs in
class User(AbstractUser):
    nickname = models.CharField(max_length=50, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    privacy_mode = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


# UserProfile handles presentation, dashboard data, preferences, stats.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="profiles/", blank=True, null=True)
    display_name = models.CharField(max_length=50, blank=True, null=True)
    profile_pic = models.ImageField(upload_to="avatars/", default="avatars/default.png")
    bio = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name or self.user.username


class Task(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    channel = models.CharField(max_length=100, blank=True, default='#reminders')
    due_date = models.DateField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Add the link to the message that was flagged to create this task
    source_message = models.ForeignKey(
        'chat.Message',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tasks'
       )
    
    # Add a description field for more detail
    description = models.TextField(blank=True)
    # updated time stamp
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['due_date', '-priority']

    def __str__(self):
        return self.title


class Channel(models.Model):
    """Represents a chat channel that users can join."""
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='channels')
    unread_count = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return f"#{self.name}"


# accounts/models.py — PomodoroSession, FIXED:
class PomodoroSession(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('break', 'Break'),
        ('completed', 'Completed'), # <-- add this
    ]
    # CHANGED: OneToOneField → ForeignKey
    user = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name='pomodoro_sessions' # note: plural now
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
    default='not_started')
    session_duration = models.PositiveIntegerField(default=25)
    break_duration = models.PositiveIntegerField(default=5)
    cycles_completed = models.PositiveIntegerField(default=0) # <-- add
    started_at = models.DateTimeField(auto_now_add=True) # <-- add
    ended_at = models.DateTimeField(null=True, blank=True) # <-- add
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.user.username} session {self.id}"


class Reminder(models.Model):
    """Time-based reminders, events, and deadlines."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=200)
    remind_at = models.DateTimeField()
    # Change channel from CharField to ForeignKey
    channel = models.ForeignKey(
        'accounts.Channel',
        on_delete=models.SET_NULL,
        null=True, blank=True
        )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['remind_at']

    def __str__(self):
        return self.title


class Activity(models.Model):
    """Recent activity feed items."""
    TYPE_CHOICES = [
        ('mention', 'Mention'),
        ('file', 'File Upload'),
        ('message', 'New Messages'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    channel = models.CharField(max_length=100)
    count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.activity_type} in {self.channel}"
