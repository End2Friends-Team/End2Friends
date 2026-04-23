from django.urls import path
from . import views

app_name = 'rooms'

urlpatterns = [
    path('', views.room_list, name='room_list'),
    path('create/', views.create_room, name='create_room'),

    # Room detail page (optional, but recommended)
    path('<int:room_id>/', views.room_detail, name='room_detail'),

    # Chat page
    path('<int:room_id>/chat/', views.room_chat, name='room_chat'),

    # Membership + invites
    path('<int:room_id>/join/', views.join_room, name='join_room'),
    path('<int:room_id>/invite/', views.send_invite, name='send_invite'),
    path('invites/', views.my_invites, name='my_invites'),
    path('invites/<int:invite_id>/accept/', views.accept_invite, name='accept_invite'),
    path('invites/<int:invite_id>/decline/', views.decline_invite, name='decline_invite'),
    path('join/<str:code>/', views.join_by_code, name='join_by_code'),
    path('<int:room_id>/delete/', views.delete_room, name='delete_room'),

    # Channel URLs
    path('<int:room_id>/channels/create/', views.create_channel, name='create_channel'),
    path('<int:room_id>/channels/<int:channel_id>/', views.channel_chat, name='channel_chat'),
    path('<int:room_id>/channels/<int:channel_id>/edit/', views.edit_channel, name='edit_channel'),
    path('<int:room_id>/channels/<int:channel_id>/delete/', views.delete_channel, name='delete_channel'),
    path('<int:room_id>/channels/<int:channel_id>/upload/', views.channel_upload_file, name='channel_upload_file'),
    path('<int:room_id>/channels/<int:channel_id>/messages/<int:message_id>/edit/', views.edit_channel_message, name='edit_channel_message'),
    path('<int:room_id>/channels/<int:channel_id>/messages/<int:message_id>/delete/', views.delete_channel_message, name='delete_channel_message'),
    
    # Pinned messages
    path('<int:room_id>/pinned-messages/', views.get_pinned_messages, name='get_pinned_messages'),
    path('<int:room_id>/channels/<int:channel_id>/messages/<int:message_id>/pin/', views.pin_message, name='pin_message'),
    path('<int:room_id>/channels/<int:channel_id>/messages/<int:message_id>/unpin/', views.unpin_message, name='unpin_message'),
    
    # Mentions
    path('mentions/', views.get_my_mentions, name='get_my_mentions'),
    path('mentions/<int:mention_id>/read/', views.mark_mention_read, name='mark_mention_read'),
    path('mentions/mark-all-read/', views.mark_all_mentions_read, name='mark_all_mentions_read'),
    
    # Read receipts
    path('<int:room_id>/channels/<int:channel_id>/mark-seen/', views.mark_messages_seen, name='mark_messages_seen'),
    path('<int:room_id>/channels/<int:channel_id>/read-status/', views.get_read_status, name='get_read_status'),
    
    # Presence
    path('<int:room_id>/presence/', views.get_room_presence, name='get_room_presence'),
]
