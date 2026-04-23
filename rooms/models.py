import uuid
import os
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


def channel_file_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'channel_files/{uuid.uuid4()}{ext}'


def generate_code():
    # Generates an 8‑character unique invite code
    return uuid.uuid4().hex[:8]


class StudyRoom(models.Model):
    ROOM_TYPE = [
        ("study", "Study"),
        ("class", "Class"),
        ("group", "Group"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE)
    is_private = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_rooms"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Auto‑generated invite code
    invite_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        default=generate_code
    )

    def __str__(self):
        return self.name


class RoomMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_memberships"
    )

    room = models.ForeignKey(
        "StudyRoom",
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default="member"
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} in {self.room} ({self.role})"


class RoomInvite(models.Model):
    room = models.ForeignKey(
        "StudyRoom",
        on_delete=models.CASCADE,
        related_name="invites"
    )

    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_invites"
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_room_invites"
    )

    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite to {self.room} for {self.invited_user}"


class Channel(models.Model):
    COLOR_CHOICES = [
        ('purple', 'Purple'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('orange', 'Orange'),
        ('pink', 'Pink'),
        ('yellow', 'Yellow'),
        ('gray', 'Gray'),
    ]

    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10, blank=True, default='')  # Channel emoji prefix
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple')

    room = models.ForeignKey(
        "StudyRoom",
        on_delete=models.CASCADE,
        related_name="room_channels"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_room_channels"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['name', 'room']

    def __str__(self):
        return f"#{self.name} in {self.room}"
    
    @property
    def display_prefix(self):
        """Return emoji if set, otherwise #"""
        return self.emoji if self.emoji else '#'


class Message(models.Model):
    channel = models.ForeignKey(
        "Channel",
        on_delete=models.CASCADE,
        related_name="messages"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="channel_messages"
    )

    content = models.TextField(blank=True)
    file = models.FileField(upload_to=channel_file_path, blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user.username}: {self.content[:30] if self.content else '[file]'}"

    @property
    def is_image(self):
        if not self.file:
            return False
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']


class PinnedMessage(models.Model):
    """Stores pinned messages for a room (across all channels)."""
    room = models.ForeignKey(
        "StudyRoom",
        on_delete=models.CASCADE,
        related_name="pinned_messages"
    )
    channel = models.ForeignKey(
        "Channel",
        on_delete=models.CASCADE,
        related_name="pinned_messages"
    )
    message = models.OneToOneField(
        "Message",
        on_delete=models.CASCADE,
        related_name="pin"
    )
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pinned_messages"
    )
    pinned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pinned_at']

    def __str__(self):
        return f"Pinned: {self.message} by {self.pinned_by}"


class MessageMention(models.Model):
    """Tracks @mentions in messages."""
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        related_name="mentions"
    )
    mentioned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions_received"
    )
    mentioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mentions_sent"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['message', 'mentioned_user']
        ordering = ['-created_at']

    def __str__(self):
        return f"@{self.mentioned_user.username} by {self.mentioned_by.username}"


class MessageReadStatus(models.Model):
    """Tracks which users have seen which messages."""
    message = models.ForeignKey(
        "Message",
        on_delete=models.CASCADE,
        related_name="read_statuses"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="read_messages"
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['message', 'user']
        ordering = ['-seen_at']

    def __str__(self):
        return f"{self.user.username} saw message {self.message_id}"


@receiver(post_save, sender=StudyRoom)
def create_default_channel(sender, instance, created, **kwargs):
    """Auto-create a 'General' channel when a new room is created."""
    if created:
        Channel.objects.create(
            name="General",
            room=instance,
            created_by=instance.created_by
        )
