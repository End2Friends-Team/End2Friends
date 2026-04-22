from django.urls import path
from . import views
from .views import people_view

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("register/", views.register_view, name="register"),
    path("people/", people_view, name="people"),
    path("profile/", views.profile_view, name="profile"),
    path("messages/", views.messages_view, name="messages_page"),
    path("settings/", views.settings_view, name="settings_page"),
    # Task actions
    path("tasks/<int:task_id>/toggle/", views.toggle_task, name="toggle_task"),
    path("tasks/<int:task_id>/delete/", views.delete_task, name="delete_task"),
    # Reminder actions
    path("reminders/add/", views.add_reminder, name="add_reminder"),
    path("reminders/<int:reminder_id>/dismiss/", views.dismiss_reminder, name="dismiss_reminder"),
    path('profile/save-avatar/', views.save_avatar, name='save_avatar'),
]