from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Conversation, Message
import json
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError

User = get_user_model()

@login_required
def inbox(request):
    conversations = Conversation.objects.filter(
        is_private=True,
        participants=request.user
    ).order_by('-messages__timestamp').distinct()
    return render(request, "chat/inbox.html", {"conversations": conversations})

@login_required
def start_dm(request, username):
    other_user = get_object_or_404(User, username=username)

    conversation = Conversation.objects.filter(
        is_private=True,
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(is_private=True)
        conversation.participants.add(request.user, other_user)

    return redirect('chat_room', room_name=conversation.room_id)

@login_required
def chat_room(request, room_name):
    conversation = get_object_or_404(Conversation, room_id=room_name)

    if request.user not in conversation.participants.all():
        return redirect('inbox')

    messages = conversation.messages.select_related('user').all()

    other_user = None
    if conversation.is_private:
        other_user = conversation.participants.exclude(id=request.user.id).first()

    try:
        from accounts.models import Channel
        channel = Channel.objects.get(name=room_name)
        channel.members.add(request.user)
    except Exception:
        pass

    user_channels = request.user.channels.all()

    return render(request, "chat/chat.html", {
        "room_name": room_name,
        "messages": messages,
        "conversation": conversation,
        "channels": user_channels,
        "other_user": other_user,
    })

@login_required
@require_POST
def delete_conversation(request, room_id):
    convo = get_object_or_404(Conversation, room_id=room_id)

    if request.user in convo.participants.all():
        convo.delete()

    return redirect('inbox')

@login_required
def edit_message(request, message_id):
    msg = Message.objects.get(pk=message_id)

    if msg.user != request.user:
        return JsonResponse({"error": "Not allowed."}, status=403)

    body = json.loads(request.body)
    new_content = body.get("content", "").strip()

    msg.content = new_content
    msg.is_edited = True
    msg.edited_at = timezone.now()
    msg.save(update_fields=["content", "is_edited", "edited_at"])

    return JsonResponse({"ok": True, "content": msg.content})


@login_required
def delete_message(request, message_id):
    msg = Message.objects.get(pk=message_id)

    if msg.user != request.user:
        return JsonResponse({"error": "Not allowed."}, status=403)

    msg.is_deleted = True
    msg.deleted_at = timezone.now()
    msg.content = ""
    msg.save(update_fields=["is_deleted", "deleted_at", "content"])

    return JsonResponse({"ok": True})


@login_required
@require_POST
def upload_file(request, room_name):
    """Handle file uploads for chat messages."""
    conversation = get_object_or_404(Conversation, room_id=room_name)

    if request.user not in conversation.participants.all():
        return JsonResponse({"error": "Not a participant"}, status=403)

    uploaded_file = request.FILES.get('file')
    message_text = request.POST.get('message', '').strip()

    if not uploaded_file:
        return JsonResponse({"error": "No file provided"}, status=400)

    try:
        # STEP 1 — Create message WITHOUT file
        msg = Message.objects.create(
            conversation=conversation,
            user=request.user,
            content=message_text,
            original_filename=uploaded_file.name
        )

        # STEP 2 — Assign file and save (this triggers Cloudinary upload)
        msg.file = uploaded_file
        msg.save()

        return JsonResponse({
            "ok": True,
            "message_id": msg.id,
            "file_url": msg.file.url if msg.file else None,
            "filename": msg.original_filename,
            "is_image": msg.is_image,
            "content": msg.content,
            "username": request.user.username,
        })

    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
