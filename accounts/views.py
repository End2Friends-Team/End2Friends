from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model
from rooms.models import StudyRoom
from chat.models import Conversation

import os
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from django.http import JsonResponse
from .models import Reminder
from datetime import datetime

User = get_user_model()

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    TaskForm,
    ChannelForm,
    UpdateProfileForm,
    UpdateUserForm,
)

from .models import (
    Task,
    Channel,
    PomodoroSession,
    Reminder,
    Activity,
)



def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/accounts/dashboard/")
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("/accounts/dashboard/")
    else:
        form = CustomAuthenticationForm()
    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def messages_view(request):
    conversations = Conversation.objects.filter(
        participants=request.user
    ).prefetch_related('participants').order_by('-id')

    return render(request, "accounts/messages.html", {
        "conversations": conversations,
    })


@login_required
def settings_view(request):
    return render(request, "accounts/settings.html")


@login_required
def dashboard_view(request):
    if request.method == "POST":
        if "add_task" in request.POST:
            form = TaskForm(request.POST)
            channel_form = ChannelForm()
            if form.is_valid():
                task = form.save(commit=False)
                task.user = request.user
                task.save()
                return redirect("dashboard")

        elif "create_channel" in request.POST:
            channel_form = ChannelForm(request.POST)
            form = TaskForm()
            if channel_form.is_valid():
                channel = channel_form.save()
                channel.members.add(request.user)
                return redirect("dashboard")

    else:
        form = TaskForm()
        channel_form = ChannelForm()

    tasks = Task.objects.filter(user=request.user, completed=False)[:5]
    channels = request.user.channels.all()[:5]
    pomodoro, _ = PomodoroSession.objects.get_or_create(user=request.user)
    reminders = Reminder.objects.filter(
        user=request.user,
        remind_at__gte=timezone.now()
    )[:5]
    activities = Activity.objects.filter(user=request.user)[:4]
    study_rooms = StudyRoom.objects.filter(memberships__user=request.user)[:4]

    recent_conversations = Conversation.objects.filter(
        participants=request.user,
        is_private=True
    ).prefetch_related('participants').order_by('-id')[:3]

    return render(
        request,
        "accounts/dashboard.html",
        {
            "tasks": tasks,
            "form": form,
            "channel_form": channel_form,
            "channels": channels,
            "pomodoro": pomodoro,
            "reminders": reminders,
            "activities": activities,
            "study_rooms": study_rooms,
            "recent_conversations": recent_conversations,
        },
    )


@login_required
def people_view(request):
    query = request.GET.get('q', '')
    users = User.objects.exclude(id=request.user.id)
    if query:
        users = users.filter(username__icontains=query)
    return render(request, "accounts/people.html", {"users": users, "query": query})

@login_required
@require_POST
def save_avatar(request):
    data = json.loads(request.body)
    public_id = data.get('public_id', '').strip()
    if public_id:
        profile = request.user.userprofile
        # Cloudinary needs the extension to generate the correct URL
        profile.profile_image = public_id + '.jpg'
        profile.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)

@login_required
def profile_view(request):
    if request.method == 'POST':

        # Avatar upload modal
        if request.POST.get('form_type') == 'avatar':
            profile_form = UpdateProfileForm(
                request.POST,
                request.FILES,
                instance=request.user.userprofile
            )
            user_form = UpdateUserForm(instance=request.user)

            if profile_form.is_valid():
                profile_form.save()
                return redirect('profile')

        # Edit profile modal
        else:
            user_form = UpdateUserForm(request.POST, instance=request.user)
            profile_form = UpdateProfileForm(
                request.POST,
                request.FILES,
                instance=request.user.userprofile
            )

            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                return redirect('profile')

    else:
        user_form = UpdateUserForm(instance=request.user)
        profile_form = UpdateProfileForm(instance=request.user.userprofile)

    return render(
        request,
        'accounts/profile.html',
        {
            'user_form': user_form,
            'profile_form': profile_form,
            'cloudinary_cloud_name': os.getenv('CLOUDINARY_CLOUD_NAME'),
            'cloudinary_upload_preset': os.getenv('CLOUDINARY_UPLOAD_PRESET'),
        }
    )



@login_required
def toggle_task(request, task_id):
    from django.http import JsonResponse
    task = Task.objects.filter(id=task_id, user=request.user).first()
    if task:
        task.completed = not task.completed
        task.save()
        return JsonResponse({'ok': True, 'completed': task.completed})
    return JsonResponse({'ok': False}, status=404)


@login_required
def delete_task(request, task_id):
    from django.http import JsonResponse
    task = Task.objects.filter(id=task_id, user=request.user).first()
    if task:
        task.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=404)


@login_required
def add_reminder(request):

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        remind_at = request.POST.get('remind_at', '')

        if title and remind_at:
            try:
                remind_datetime = datetime.fromisoformat(remind_at)
                Reminder.objects.create(
                    user=request.user,
                    title=title,
                    remind_at=remind_datetime
                )
                return redirect('dashboard')
            except ValueError:
                pass

    return redirect('dashboard')


@login_required
def dismiss_reminder(request, reminder_id):
    from django.http import JsonResponse
    reminder = Reminder.objects.filter(id=reminder_id, user=request.user).first()
    if reminder:
        reminder.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=404)
