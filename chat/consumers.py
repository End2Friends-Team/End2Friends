from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
import traceback


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        try:
            self.room_id = self.scope["url_route"]["kwargs"]["room_name"]
            self.room_group_name = f"chat_{self.room_id}"

            # AUTH GUARD — reject unauthenticated users immediately
            user = self.scope["user"]
            if not user.is_authenticated:
                await self.close()
                return

            # PARTICIPANT CHECK — user must be in this conversation
            is_member = await self.user_in_conversation(user, self.room_id)
            if not is_member:
                await self.close()
                return

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)

            await self.accept()
            print(f"[WS] Connected: {self.room_id} | User: {user}")

        except Exception as e:
            print(f"[WS ERROR] Connect failed: {e}")
            traceback.print_exc()
            await self.close()

    async def disconnect(self, close_code):
        print(f"[WS] Disconnected: code={close_code}")
        try:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
        except Exception as e:
            print(f"[WS ERROR] Disconnect error: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            message = data.get("message", "").strip()
            user = self.scope["user"]
            msg_type = data.get("type", "chat")

            print(f"[WS] Message from {user}: {message}")

            if not user.is_authenticated:
                print("[WS] Rejected - unauthenticated user")
                return
            
            if msg_type == "edit":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "message_edited", "message_id": data.get("message_id"), "content": data.get("content", "")},
                )
                return

            if msg_type == "delete":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "message_deleted", "message_id": data.get("message_id")},
                )
                return

            if msg_type == "file_upload":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "file_uploaded",
                        "message_id": data.get("message_id"),
                        "file_url": data.get("file_url"),
                        "filename": data.get("filename"),
                        "is_image": data.get("is_image"),
                        "content": data.get("content", ""),
                        "username": data.get("username"),
                    },
                )
                return

            if not message:
                print("[WS] Rejected - empty message")
                return            

            save_id = await self.save_message(user, self.room_id, message)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "username": user.username,
                    "message_id": save_id,
                },
            )

        except Exception as e:
            print(f"[WS ERROR] Receive failed: {e}")
            traceback.print_exc()

    async def chat_message(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "message": event["message"],
                        "username": event["username"],
                    }
                )
            )
        except Exception as e:
            print(f"[WS ERROR] Send failed: {e}")

    async def message_edited(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "message_edited",
                "message_id": event["message_id"],
                "content": event["content"],
            }))
        except Exception as e:
            print(f"[WS ERROR] message_edited failed: {e}")

    async def message_deleted(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "message_deleted",
                "message_id": event["message_id"],
            }))
        except Exception as e:
            print(f"[WS ERROR] message_deleted failed: {e}")

    async def file_uploaded(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "file_uploaded",
                "message_id": event["message_id"],
                "file_url": event["file_url"],
                "filename": event["filename"],
                "is_image": event["is_image"],
                "content": event["content"],
                "username": event["username"],
            }))
        except Exception as e:
            print(f"[WS ERROR] file_uploaded failed: {e}")


    @database_sync_to_async
    def save_message(self, user, room_id, content):
        from .models import Conversation, Message

        try:
            conversation = Conversation.objects.get(room_id=room_id)
            msg = Message.objects.create(
                conversation=conversation, user=user, content=content
            )
            print(f"[WS] Saved message id={msg.id}")
            return msg.id
        except Conversation.DoesNotExist:
            print(f"[WS ERROR] Conversation not found for room_id={room_id}")
        except Exception as e:
            print(f"[WS ERROR] Save failed: {e}")
            traceback.print_exc()


    @database_sync_to_async
    def user_in_conversation(self, user, room_id):
        from .models import Conversation

        return Conversation.objects.filter(room_id=room_id, participants=user).exists()


class ChannelConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for room channel chat."""

    async def connect(self):
        try:
            self.channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
            self.room_group_name = f"channel_{self.channel_id}"

            user = self.scope["user"]
            if not user.is_authenticated:
                await self.close()
                return

            # Check if user is a member of the room this channel belongs to
            is_member = await self.user_is_channel_member(user, self.channel_id)
            if not is_member:
                await self.close()
                return

            # Get room_id for presence group
            self.room_id = await self.get_room_id_for_channel(self.channel_id)
            self.presence_group_name = f"presence_{self.room_id}"

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.channel_layer.group_add(self.presence_group_name, self.channel_name)
            await self.accept()
            
            # Update user presence
            await self.update_user_presence(user, True)
            
            # Broadcast presence update to room
            await self.channel_layer.group_send(
                self.presence_group_name,
                {
                    "type": "presence_update",
                    "user_id": user.id,
                    "username": user.username,
                    "is_online": True,
                }
            )
            
            print(f"[WS Channel] Connected: channel={self.channel_id} | User: {user}")

        except Exception as e:
            print(f"[WS Channel ERROR] Connect failed: {e}")
            traceback.print_exc()
            await self.close()

    async def disconnect(self, close_code):
        print(f"[WS Channel] Disconnected: code={close_code}")
        try:
            user = self.scope["user"]
            
            # Update user presence
            if user.is_authenticated:
                is_still_online = await self.update_user_presence(user, False)
                
                # Broadcast presence update only if fully offline
                if not is_still_online and hasattr(self, 'presence_group_name'):
                    await self.channel_layer.group_send(
                        self.presence_group_name,
                        {
                            "type": "presence_update",
                            "user_id": user.id,
                            "username": user.username,
                            "is_online": False,
                        }
                    )
            
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
            if hasattr(self, 'presence_group_name'):
                await self.channel_layer.group_discard(
                    self.presence_group_name, self.channel_name
                )
        except Exception as e:
            print(f"[WS Channel ERROR] Disconnect error: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            message = data.get("message", "").strip()
            msg_type = data.get("type", "chat")
            user = self.scope["user"]

            print(f"[WS Channel] Message from {user}: {message}")

            if not user.is_authenticated:
                return

            # Handle file upload broadcast
            if msg_type == "file_upload":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "file_uploaded",
                        "message_id": data.get("message_id"),
                        "file_url": data.get("file_url"),
                        "filename": data.get("filename"),
                        "is_image": data.get("is_image"),
                        "content": data.get("content", ""),
                        "username": data.get("username"),
                    },
                )
                return

            # Handle pin update broadcast
            if msg_type == "pin_update":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "pin_updated",
                        "message_id": data.get("message_id"),
                        "pinned": data.get("pinned"),
                        "username": user.username,
                    },
                )
                return

            # Handle read receipt broadcast
            if msg_type == "read_receipt":
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "read_receipt_update",
                        "message_ids": data.get("message_ids", []),
                        "user_id": user.id,
                        "username": user.username,
                    },
                )
                return

            # Handle mention notification
            if msg_type == "mention_notification":
                # Send to mentioned user's personal channel
                mentioned_user_id = data.get("mentioned_user_id")
                if mentioned_user_id:
                    await self.channel_layer.group_send(
                        f"user_{mentioned_user_id}",
                        {
                            "type": "mention_received",
                            "message_id": data.get("message_id"),
                            "channel_id": self.channel_id,
                            "mentioned_by": user.username,
                            "preview": data.get("preview", ""),
                        },
                    )
                return

            if not message:
                return

            # Save message to database
            await self.save_channel_message(user, self.channel_id, message)

            # Broadcast to group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "user": user.username,
                },
            )

        except Exception as e:
            print(f"[WS Channel ERROR] Receive failed: {e}")
            traceback.print_exc()

    async def chat_message(self, event):
        try:
            await self.send(
                text_data=json.dumps({
                    "message": event["message"],
                    "user": event["user"],
                })
            )
        except Exception as e:
            print(f"[WS Channel ERROR] Send failed: {e}")

    async def file_uploaded(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "file_uploaded",
                "message_id": event["message_id"],
                "file_url": event["file_url"],
                "filename": event["filename"],
                "is_image": event["is_image"],
                "content": event["content"],
                "username": event["username"],
            }))
        except Exception as e:
            print(f"[WS Channel ERROR] file_uploaded failed: {e}")

    async def pin_updated(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "pin_updated",
                "message_id": event["message_id"],
                "pinned": event["pinned"],
                "username": event["username"],
            }))
        except Exception as e:
            print(f"[WS Channel ERROR] pin_updated failed: {e}")

    async def presence_update(self, event):
        """Send presence update to client."""
        try:
            await self.send(text_data=json.dumps({
                "type": "presence_update",
                "user_id": event["user_id"],
                "username": event["username"],
                "is_online": event["is_online"],
            }))
        except Exception as e:
            print(f"[WS Channel ERROR] presence_update failed: {e}")

    async def read_receipt_update(self, event):
        """Send read receipt update to client."""
        try:
            await self.send(text_data=json.dumps({
                "type": "read_receipt_update",
                "message_ids": event["message_ids"],
                "user_id": event["user_id"],
                "username": event["username"],
            }))
        except Exception as e:
            print(f"[WS Channel ERROR] read_receipt_update failed: {e}")

    async def mention_received(self, event):
        """Send mention notification to client."""
        try:
            await self.send(text_data=json.dumps({
                "type": "mention_received",
                "message_id": event["message_id"],
                "channel_id": event["channel_id"],
                "mentioned_by": event["mentioned_by"],
                "preview": event["preview"],
            }))
        except Exception as e:
            print(f"[WS Channel ERROR] mention_received failed: {e}")

    @database_sync_to_async
    def user_is_channel_member(self, user, channel_id):
        from rooms.models import Channel, RoomMembership

        try:
            channel = Channel.objects.get(id=channel_id)
            return RoomMembership.objects.filter(user=user, room=channel.room).exists()
        except Channel.DoesNotExist:
            return False

    @database_sync_to_async
    def get_room_id_for_channel(self, channel_id):
        from rooms.models import Channel
        try:
            channel = Channel.objects.get(id=channel_id)
            return channel.room_id
        except Channel.DoesNotExist:
            return None

    @database_sync_to_async
    def update_user_presence(self, user, is_connecting):
        """Update user's online status. Returns True if user is still online (other connections)."""
        from django.utils import timezone
        try:
            profile = user.userprofile
            if is_connecting:
                profile.connection_count += 1
                profile.is_online = True
            else:
                profile.connection_count = max(0, profile.connection_count - 1)
                if profile.connection_count == 0:
                    profile.is_online = False
                    profile.last_seen = timezone.now()
            profile.save()
            return profile.is_online
        except Exception as e:
            print(f"[WS Channel ERROR] update_user_presence failed: {e}")
            return False

    @database_sync_to_async
    def save_channel_message(self, user, channel_id, content):
        from rooms.models import Channel, Message
        from rooms.views import create_mentions_for_message

        try:
            channel = Channel.objects.get(id=channel_id)
            msg = Message.objects.create(
                channel=channel,
                user=user,
                content=content
            )
            # Parse and create mentions
            create_mentions_for_message(msg, user)
            print(f"[WS Channel] Saved message id={msg.id}")
            return msg.id
        except Channel.DoesNotExist:
            print(f"[WS Channel ERROR] Channel not found: {channel_id}")
        except Exception as e:
            print(f"[WS Channel ERROR] Save failed: {e}")
            traceback.print_exc()
        return None
