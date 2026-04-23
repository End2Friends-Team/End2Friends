from django.db import models
from django.contrib.auth import get_user_model
import shortuuid
import os
import uuid
from .validators import validate_uploaded_file
from cloudinary_storage.storage import MediaCloudinaryStorage


User = get_user_model()

# represents any chat space (DM, group chat, etc.)
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


def upload_to_uuid(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'chat_files/{uuid.uuid4()}{ext}'


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    file = models.FileField(
        storage=MediaCloudinaryStorage(),
        upload_to=upload_to_uuid,
        blank=True,
        null=True,
        validators=[validate_uploaded_file]
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
            return os.path.basename(self.file.name)
        return None

    @property
    def is_image(self):
        """
        Safe image detection:
        - Works with Cloudinary (no local file access)
        - Handles missing or broken file paths
        - Uses MIME type when available
        - Falls back to extension check
        """
        if not self.file:
            return False

        # Try MIME type first (Cloudinary sometimes provides this)
        content_type = getattr(self.file, 'content_type', None)
        if isinstance(content_type, str) and content_type.startswith('image/'):
            return True

        # Safe fallback: check extension
        name = getattr(self.file, 'name', '')
        if not isinstance(name, str) or '.' not in name:
            return False

        ext = os.path.splitext(name)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
