from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import json
import re
import os
from .models import StudyRoom, RoomMembership, RoomInvite, Channel, Message, MessageMention, MessageReadStatus

User = get_user_model()


@login_required
def room_list(request):
    my_rooms = StudyRoom.objects.filter(memberships__user=request.user)
    public_rooms = StudyRoom.objects.filter(
        is_private=False
    ).exclude(memberships__user=request.user)
    return render(request, 'rooms/room_list.html', {
        'my_rooms': my_rooms,
        'public_rooms': public_rooms,
    })


@login_required
def create_room(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        room_type = request.POST.get('room_type', 'study')
        is_private = request.POST.get('is_private') == 'on'

        room = StudyRoom.objects.create(
            name=name,
            description=description,
            room_type=room_type,
            is_private=is_private,
            created_by=request.user
        )

        RoomMembership.objects.create(
            user=request.user, room=room, role='owner'
        )

        return redirect('rooms:room_chat', room_id=room.id)

    return render(request, 'rooms/create_room.html')


@login_required
def join_room(request, room_id):
    room = get_object_or_404(StudyRoom, id=room_id)

    if not room.is_private:
        RoomMembership.objects.get_or_create(
            user=request.user, room=room,
            defaults={'role': 'member'}
        )

    return redirect('rooms:room_chat', room_id=room.id)


@login_required
def send_invite(request, room_id):
    if request.method != 'POST':
        return redirect('rooms:room_list')

    room = get_object_or_404(StudyRoom, id=room_id)

    is_member = RoomMembership.objects.filter(
        user=request.user, room=room
    ).exists()

    if not is_member:
        return redirect('rooms:room_list')

    username = request.POST.get('username')
    invited_user = get_object_or_404(User, username=username)

    already_member = RoomMembership.objects.filter(
        user=invited_user, room=room
    ).exists()

    if already_member:
        return redirect('rooms:room_chat', room_id=room.id)

    already_invited = RoomInvite.objects.filter(
        invited_user=invited_user, room=room, accepted=False
    ).exists()

    if already_invited:
        return redirect('rooms:room_chat', room_id=room.id)

    RoomInvite.objects.create(
        room=room,
        invited_user=invited_user,
        invited_by=request.user
    )

    return redirect('rooms:room_chat', room_id=room.id)


@login_required
def accept_invite(request, invite_id):
    invite = get_object_or_404(
        RoomInvite, id=invite_id, invited_user=request.user
    )

    invite.accepted = True
    invite.save()

    RoomMembership.objects.get_or_create(
        user=request.user,
        room=invite.room,
        defaults={'role': 'member'}
    )

    return redirect('rooms:room_chat', room_id=invite.room.id)


@login_required
def decline_invite(request, invite_id):
    invite = get_object_or_404(
        RoomInvite, id=invite_id, invited_user=request.user
    )

    invite.delete()
    return redirect('dashboard')


@login_required
def my_invites(request):
    invites = RoomInvite.objects.filter(
        invited_user=request.user,
        accepted=False
    ).select_related('room', 'invited_by')

    return render(request, 'rooms/invites.html', {'invites': invites})


@login_required
def room_detail(request, room_id):
    room = get_object_or_404(StudyRoom, id=room_id)

    membership = RoomMembership.objects.filter(
        user=request.user, room=room
    ).first()

    return render(request, "rooms/room_detail.html", {
        "room": room,
        "membership": membership,
    })


@login_required
def room_chat(request, room_id):
    room = get_object_or_404(StudyRoom, id=room_id)

    membership = RoomMembership.objects.filter(
        user=request.user, room=room
    ).first()

    if not membership and room.is_private:
        return redirect('rooms:room_list')

    members = RoomMembership.objects.filter(
        room=room
    ).select_related('user')

    # Get all channels for this room
    channels = room.room_channels.all().order_by('created_at')

    return render(request, 'rooms/chat.html', {
        'room': room,
        'members': members,
        'membership': membership,
        'channels': channels,
    })

    
    
@login_required
def join_by_code(request, code):
    room = get_object_or_404(StudyRoom, invite_code=code)

    RoomMembership.objects.get_or_create(
        user=request.user,
        room=room,
        defaults={'role': 'member'}
    )

    return redirect('rooms:room_chat', room_id=room.id)


@login_required
def delete_room(request, room_id):
    room = get_object_or_404(StudyRoom, id=room_id)
    
    # Only the owner can delete
    membership = RoomMembership.objects.filter(
        user=request.user, room=room, role='owner'
    ).first()
    
    if not membership:
        return redirect('rooms:room_list')
    
    if request.method == 'POST':
        room.delete()
        return redirect('dashboard')
    
    return redirect('rooms:room_detail', room_id=room_id)


@login_required
def create_channel(request, room_id):
    """Create a new channel - owner only."""
    room = get_object_or_404(StudyRoom, id=room_id)
    
    # Check if user is owner
    membership = RoomMembership.objects.filter(
        user=request.user, room=room, role='owner'
    ).first()
    
    if not membership:
        messages.error(request, "Only the room owner can create channels.")
        return redirect('rooms:room_chat', room_id=room_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        
        # Validate blank name
        if not name:
            messages.error(request, "Channel name cannot be empty.")
            return redirect('rooms:room_chat', room_id=room_id)
        
        emoji = request.POST.get('emoji', '').strip()
        color = request.POST.get('color', 'purple')
        
        # Try to create (unique_together will catch duplicates)
        try:
            Channel.objects.create(
                name=name,
                emoji=emoji,
                color=color,
                room=room,
                created_by=request.user
            )
            messages.success(request, f"Channel '{emoji or '#'}{name}' created!")
        except IntegrityError:
            messages.error(request, f"A channel named '{name}' already exists.")
        
        return redirect('rooms:room_chat', room_id=room_id)
    
    return redirect('rooms:room_chat', room_id=room_id)


@login_required
def edit_channel(request, room_id, channel_id):
    """Edit a channel - owner only."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check if user is owner
    membership = RoomMembership.objects.filter(
        user=request.user, room=room, role='owner'
    ).first()
    
    if not membership:
        messages.error(request, "Only the room owner can edit channels.")
        return redirect('rooms:channel_chat', room_id=room_id, channel_id=channel_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        emoji = request.POST.get('emoji', '').strip()
        color = request.POST.get('color', 'purple')
        
        if not name:
            messages.error(request, "Channel name cannot be empty.")
            return redirect('rooms:channel_chat', room_id=room_id, channel_id=channel_id)
        
        # Check for duplicate name (excluding current channel)
        if Channel.objects.filter(room=room, name=name).exclude(id=channel_id).exists():
            messages.error(request, f"A channel named '{name}' already exists.")
            return redirect('rooms:channel_chat', room_id=room_id, channel_id=channel_id)
        
        channel.name = name
        channel.emoji = emoji
        channel.color = color
        channel.save()
        messages.success(request, f"Channel updated!")
        return redirect('rooms:channel_chat', room_id=room_id, channel_id=channel_id)
    
    return redirect('rooms:channel_chat', room_id=room_id, channel_id=channel_id)


@login_required
def delete_channel(request, room_id, channel_id):
    """Delete a channel - owner only."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check if user is owner
    membership = RoomMembership.objects.filter(
        user=request.user, room=room, role='owner'
    ).first()
    
    if not membership:
        messages.error(request, "Only the room owner can delete channels.")
        return redirect('rooms:room_chat', room_id=room_id)
    
    if request.method == 'POST':
        channel_name = channel.name
        channel.delete()
        messages.success(request, f"Channel '#{channel_name}' deleted.")
        return redirect('rooms:room_chat', room_id=room_id)
    
    return redirect('rooms:room_chat', room_id=room_id)


@login_required
def channel_chat(request, room_id, channel_id):
    """View a channel's chat - members only."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check if user is a member
    membership = RoomMembership.objects.filter(
        user=request.user, room=room
    ).first()
    
    if not membership:
        messages.error(request, "You must be a member to view this channel.")
        return redirect('rooms:room_list')
    
    # Get all channels for sidebar
    channels = room.room_channels.all().order_by('created_at')
    
    # Get messages for this channel (prefetch pin relation)
    from django.db.models import Prefetch
    channel_messages = channel.messages.select_related('user').prefetch_related(
        Prefetch('pin')
    ).order_by('timestamp')
    
    # Get room members
    members = RoomMembership.objects.filter(room=room).select_related('user')
    
    return render(request, 'rooms/channel_chat.html', {
        'room': room,
        'channel': channel,
        'channels': channels,
        'channel_messages': channel_messages,
        'members': members,
        'membership': membership,
    })


@login_required
@require_POST
def channel_upload_file(request, room_id, channel_id):
    """Handle file uploads for channel messages."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    uploaded_file = request.FILES.get('file')
    message_text = request.POST.get('message', '').strip()
    
    if not uploaded_file:
        return JsonResponse({"error": "No file provided"}, status=400)
    
    try:
        msg = Message.objects.create(
            channel=channel,
            user=request.user,
            content=message_text,
            file=uploaded_file,
            original_filename=uploaded_file.name
        )
        
        # Construct proper file URL (handles both Cloudinary and local storage)
        file_url = None
        if msg.file:
            cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
            if cloud_name:
                # Cloudinary URL - use raw/upload for MediaCloudinaryStorage files
                file_url = f'https://res.cloudinary.com/{cloud_name}/raw/upload/{msg.file.name}'
            else:
                # Local storage URL
                file_url = msg.file.url
        
        return JsonResponse({
            "ok": True,
            "message_id": msg.id,
            "file_url": file_url,
            "filename": msg.original_filename,
            "is_image": msg.is_image,
            "content": msg.content,
            "username": request.user.username,
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def edit_channel_message(request, room_id, channel_id, message_id):
    """Edit a channel message."""
    msg = get_object_or_404(Message, id=message_id, channel_id=channel_id)
    
    if msg.user != request.user:
        return JsonResponse({"error": "Not allowed"}, status=403)
    
    try:
        body = json.loads(request.body)
        new_content = body.get("content", "").strip()
        if not new_content:
            return JsonResponse({"error": "Content required"}, status=400)
        
        msg.content = new_content
        msg.save(update_fields=["content"])
        
        return JsonResponse({"ok": True, "content": msg.content})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def delete_channel_message(request, room_id, channel_id, message_id):
    """Delete a channel message."""
    msg = get_object_or_404(Message, id=message_id, channel_id=channel_id)
    
    if msg.user != request.user:
        return JsonResponse({"error": "Not allowed"}, status=403)
    
    msg.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def pin_message(request, room_id, channel_id, message_id):
    """Pin a message in a room."""
    from .models import PinnedMessage
    
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    msg = get_object_or_404(Message, id=message_id, channel=channel)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    # Check if already pinned
    if hasattr(msg, 'pin'):
        return JsonResponse({"error": "Already pinned"}, status=400)
    
    # Create pin
    pin = PinnedMessage.objects.create(
        room=room,
        channel=channel,
        message=msg,
        pinned_by=request.user
    )
    
    return JsonResponse({
        "ok": True,
        "pin_id": pin.id,
        "message_id": msg.id,
        "pinned_by": request.user.username,
        "pinned_at": pin.pinned_at.isoformat(),
    })


@login_required
@require_POST
def unpin_message(request, room_id, channel_id, message_id):
    """Unpin a message from a room."""
    from .models import PinnedMessage
    
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    msg = get_object_or_404(Message, id=message_id, channel=channel)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    # Find and delete pin
    try:
        pin = PinnedMessage.objects.get(message=msg)
        pin.delete()
        return JsonResponse({"ok": True, "message_id": msg.id})
    except PinnedMessage.DoesNotExist:
        return JsonResponse({"error": "Not pinned"}, status=400)


@login_required
def get_pinned_messages(request, room_id):
    """Get all pinned messages for a room."""
    from .models import PinnedMessage
    
    room = get_object_or_404(StudyRoom, id=room_id)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    pins = PinnedMessage.objects.filter(room=room).select_related(
        'message', 'message__user', 'channel', 'pinned_by'
    )
    
    pinned_list = []
    for pin in pins:
        msg = pin.message
        # Build preview text
        if msg.content:
            preview = msg.content[:50] + ('...' if len(msg.content) > 50 else '')
        elif msg.file:
            if msg.is_image:
                preview = "📷 Image"
            else:
                preview = f"📎 {msg.original_filename}"
        else:
            preview = "[Empty message]"
        
        pinned_list.append({
            "pin_id": pin.id,
            "message_id": msg.id,
            "channel_id": pin.channel.id,
            "channel_name": pin.channel.name,
            "channel_emoji": pin.channel.emoji,
            "username": msg.user.username,
            "content": msg.content,
            "preview": preview,
            "timestamp": msg.timestamp.isoformat(),
            "is_image": msg.is_image,
            "file_url": msg.file.url if msg.file else None,
            "filename": msg.original_filename,
            "pinned_by": pin.pinned_by.username,
            "pinned_at": pin.pinned_at.isoformat(),
        })
    
    return JsonResponse({"ok": True, "pinned": pinned_list, "count": len(pinned_list)})


# ========== MENTION FUNCTIONS ==========

def parse_mentions(content, room):
    """Extract @username mentions from message content and return valid room members."""
    if not content:
        return []
    
    # Find all @username patterns
    pattern = r'@(\w+)'
    usernames = re.findall(pattern, content)
    
    if not usernames:
        return []
    
    # Get valid room members with these usernames
    room_member_ids = RoomMembership.objects.filter(room=room).values_list('user_id', flat=True)
    valid_users = User.objects.filter(
        username__in=usernames,
        id__in=room_member_ids
    )
    
    return list(valid_users)


def create_mentions_for_message(message, mentioned_by):
    """Create mention records for a message. Call after message creation/edit."""
    room = message.channel.room
    mentioned_users = parse_mentions(message.content, room)
    
    # Don't mention yourself
    mentioned_users = [u for u in mentioned_users if u.id != mentioned_by.id]
    
    # Delete old mentions for this message (in case of edit)
    MessageMention.objects.filter(message=message).exclude(
        mentioned_user__in=mentioned_users
    ).delete()
    
    # Create new mentions (ignore duplicates)
    for user in mentioned_users:
        MessageMention.objects.get_or_create(
            message=message,
            mentioned_user=user,
            defaults={'mentioned_by': mentioned_by}
        )


@login_required
def get_my_mentions(request):
    """Get unread mentions for the current user."""
    base_qs = MessageMention.objects.filter(mentioned_user=request.user)
    unread_count = base_qs.filter(is_read=False).count()
    
    mentions = base_qs.select_related(
        'message', 'message__channel', 'message__channel__room', 'message__user', 'mentioned_by'
    ).order_by('-created_at')[:50]
    
    mention_list = []
    for m in mentions:
        msg = m.message
        channel = msg.channel
        room = channel.room
        
        # Build preview
        if msg.content:
            preview = msg.content[:60] + ('...' if len(msg.content) > 60 else '')
        else:
            preview = "[File attachment]"
        
        mention_list.append({
            "mention_id": m.id,
            "message_id": msg.id,
            "channel_id": channel.id,
            "channel_name": channel.name,
            "channel_emoji": channel.emoji,
            "room_id": room.id,
            "room_name": room.name,
            "mentioned_by": m.mentioned_by.username,
            "preview": preview,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat(),
            "timestamp": msg.timestamp.isoformat(),
        })
    
    return JsonResponse({
        "ok": True,
        "mentions": mention_list,
        "unread_count": unread_count
    })


@login_required
@require_POST
def mark_mention_read(request, mention_id):
    """Mark a specific mention as read."""
    mention = get_object_or_404(MessageMention, id=mention_id, mentioned_user=request.user)
    mention.is_read = True
    mention.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def mark_all_mentions_read(request):
    """Mark all mentions as read for the current user."""
    MessageMention.objects.filter(
        mentioned_user=request.user,
        is_read=False
    ).update(is_read=True)
    return JsonResponse({"ok": True})


# ========== READ RECEIPTS FUNCTIONS ==========

@login_required
@require_POST
def mark_messages_seen(request, room_id, channel_id):
    """Mark messages as seen by the current user."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    try:
        data = json.loads(request.body)
        message_ids = data.get('message_ids', [])
    except json.JSONDecodeError:
        message_ids = []
    
    if not message_ids:
        # Mark all messages in channel as seen
        message_ids = list(channel.messages.values_list('id', flat=True))
    
    # Create read status records (ignore duplicates)
    for msg_id in message_ids:
        try:
            MessageReadStatus.objects.get_or_create(
                message_id=msg_id,
                user=request.user
            )
        except Exception:
            pass
    
    return JsonResponse({"ok": True, "marked_count": len(message_ids)})


@login_required
def get_read_status(request, room_id, channel_id):
    """Get read status for messages in a channel."""
    room = get_object_or_404(StudyRoom, id=room_id)
    channel = get_object_or_404(Channel, id=channel_id, room=room)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    # Get read statuses for recent messages
    from django.db.models import Count
    
    message_ids = list(channel.messages.order_by('-timestamp')[:100].values_list('id', flat=True))
    
    read_data = {}
    for msg_id in message_ids:
        statuses = MessageReadStatus.objects.filter(message_id=msg_id).select_related('user')
        readers = [s.user.username for s in statuses]
        read_data[msg_id] = {
            "count": len(readers),
            "readers": readers[:5],  # Limit to 5 usernames
            "has_more": len(readers) > 5
        }
    
    return JsonResponse({"ok": True, "read_data": read_data})


# ========== PRESENCE FUNCTIONS ==========

@login_required
def get_room_presence(request, room_id):
    """Get online/offline status for all room members."""
    room = get_object_or_404(StudyRoom, id=room_id)
    
    # Check membership
    if not RoomMembership.objects.filter(user=request.user, room=room).exists():
        return JsonResponse({"error": "Not a member"}, status=403)
    
    members = RoomMembership.objects.filter(room=room).select_related('user', 'user__userprofile')
    
    presence_list = []
    for membership in members:
        user = membership.user
        try:
            profile = user.userprofile
            is_online = profile.is_online
            last_seen = profile.last_seen.isoformat() if profile.last_seen else None
        except Exception:
            is_online = False
            last_seen = None
        
        presence_list.append({
            "user_id": user.id,
            "username": user.username,
            "is_online": is_online,
            "last_seen": last_seen,
            "role": membership.role,
        })
    
    # Sort: online users first
    presence_list.sort(key=lambda x: (not x['is_online'], x['username'].lower()))
    
    return JsonResponse({
        "ok": True,
        "presence": presence_list,
        "online_count": sum(1 for p in presence_list if p['is_online'])
    })
