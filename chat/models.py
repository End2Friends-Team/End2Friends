from django.db import models
from django.contrib.auth import get_user_model
import shortuuid
import os
import uuid
from .validators import validate_uploaded_file

User = get_user_model()

# represents any chat space (DM, group chat, etc.)
class Conversation(models.Model):
    # a name for the conversation
    name = models.CharField(max_length=255, blank=True, null=True)

    # unique room identifier
    room_id = models.CharField(max_length=50, unique=True, blank=True)

    # whether this is a private dm
    is_private = models.BooleanField(default=False)

    # user who created or manages the conversation
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='administered_conversations'
    )

    # users who are part of the conversation
    participants = models.ManyToManyField(
        User,
        related_name='conversations',
        blank=True
    )

    # users currently online in this conversation
    users_online = models.ManyToManyField(
        User,
        related_name='online_in_conversations',
        blank=True
    )

    # auto-generate a room ID if one doesn't exist
    def save(self, *args, **kwargs):
        if not self.room_id:
            self.room_id = shortuuid.uuid()
        super().save(*args, **kwargs)

    # show name if available, otherwise fallback to room ID
    def __str__(self):
        return self.name or f"DM({self.room_id})"


def upload_to_uuid(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f'chat_files/{uuid.uuid4()}{ext}'


# represents a single message inside a conversation
class Message(models.Model):
    # the conversation this message belongs to
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    # the user who sent the message
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    file = models.FileField(
        upload_to=upload_to_uuid,
        blank=True,
        null=True,
        validators=[validate_uploaded_file]
    )

    original_filename = models.CharField(max_length=255, blank=True)

    # text content of the message
    content = models.TextField(blank=True)

    # when the message was created
    timestamp = models.DateTimeField(auto_now_add=True)

    # editing
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    # deleting (soft delete)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # pinning / flagging
    is_pinned = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        # pinned messages first, then chronological
        ordering = ["-is_pinned", "timestamp"]

    # show username and either text or "[file]" or "[deleted]"
    def __str__(self):
        if self.is_deleted:
            preview = "[deleted]"
        else:
            preview = self.content if self.content else "[file]"
        return f"{self.user.username}: {preview}"

    # return just the file name (not the full path)
    @property
    def filename(self):
        if self.file:
            return os.path.basename(self.file.name)
        return None

    # check if uploaded file is an image by extension
    # (Image.open won't work with Cloudinary-stored files — no local path)
@property
def is_image(self):
    if not self.file:
        return False

    # Try MIME type first (Cloudinary provides this)
    content_type = getattr(self.file, 'content_type', None)
    if content_type and content_type.startswith('image/'):
        return True

    # Fallback to extension check (safe, no file open)
    ext = os.path.splitext(self.file.name)[1].lower()
    return ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']

