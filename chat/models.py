from django.db import models
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
import shortuuid
import os
import uuid
from .validators import validate_uploaded_file

User = get_user_model()

class Conversation(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    room_id = models.CharField(max_length=50, unique=True, blank=True)
    is_private = models.BooleanField(default=False)

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='administered_conversations'
    )

    participants = models.ManyToManyField(
        User,
        related_name='conversations',
        blank=True
    )

    users_online = models.ManyToManyField(
        User,
        related_name='online_in_conversations',
        blank=True
    )

    def save(self, *args, **kwargs):
        if not self.room_id:
            self.room_id = shortuuid.uuid()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or f"DM({self.room_id})"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # FIX: CloudinaryField instead of FileField
    file = CloudinaryField(
        'file',
        folder='chat_files',
        blank=True,
        null=True
    )

    original_filename = models.CharField(max_length=255, blank=True)
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    is_pinned = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-is_pinned", "timestamp"]

    def __str__(self):
        if self.is_deleted:
            preview = "[deleted]"
        else:
            preview = self.content if self.content else "[file]"
        return f"{self.user.username}: {preview}"

    @property
    def filename(self):
        if self.file:
            return os.path.basename(str(self.file))
        return None

    @property
    def is_image(self):
        if not self.file:
            return False

        name = str(self.file)
        ext = os.path.splitext(name)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
