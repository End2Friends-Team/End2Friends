from django.urls import path
from . import views

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("dm/<str:username>/", views.start_dm, name="start_dm"),
    path("delete/<str:room_id>/", views.delete_conversation, name="delete_conversation"),
    path("messages/<int:message_id>/edit/", views.edit_message, name="edit_message"),
    path("messages/<int:message_id>/delete/", views.delete_message, name="delete_message"),
    path("<str:room_name>/upload/", views.upload_file, name="upload_file"),
    path("<str:room_name>/", views.chat_room, name="chat_room"),
]