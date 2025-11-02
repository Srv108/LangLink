# main/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Message, ChatRoom

logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.room_group_name = f'chat_{self.room_id}'
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            logger.info(f"WebSocket connected to room: {self.room_id}")
            
            # Send message history on connect
            await self.send_message_history()
            
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()
            sender_id = text_data_json.get('sender_id')
            
            if not all([message, sender_id, self.room_id]):
                logger.error("Missing required fields in message")
                return

            # 1. First save the message to the database
            message_obj = await self.save_message(sender_id, message)
            if not message_obj:
                logger.error("Failed to save message to database")
                return
                
            logger.info(f"Message saved to database. ID: {message_obj.id}, Room: {self.room_id}")

            # 2. Then send the message to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': sender_id,
                    'sender_username': message_obj.sender.username,
                    'timestamp': message_obj.timestamp.isoformat(),
                    'message_id': str(message_obj.id),
                    'room_id': str(self.room_id)
                }
            )

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

    @database_sync_to_async
    def save_message(self, sender_id, message):
        try:
            sender = User.objects.get(id=sender_id)
            room = ChatRoom.objects.get(id=self.room_id)
            return Message.objects.create(
                room=room,
                sender=sender,
                content=message
            )
        except (User.DoesNotExist, ChatRoom.DoesNotExist) as e:
            logger.error(f"User or Room not found: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            return None

    async def chat_message(self, event):
        """Receive message from room group and send to WebSocket"""
        try:
            message_data = {
                'type': 'chat_message',
                'message': event['message'],
                'sender_id': event['sender_id'],
                'sender_username': event.get('sender_username', ''),
                'timestamp': event['timestamp'],
                'message_id': event.get('message_id', ''),
                'room_id': event.get('room_id', '')
            }
            logger.info(f"Sending message to WebSocket: {message_data}")
            await self.send(text_data=json.dumps(message_data))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {str(e)}")

    @database_sync_to_async
    def get_message_history(self):
        """Retrieve message history for the room"""
        return list(Message.objects.filter(
            room_id=self.room_id
        ).select_related('sender').order_by('timestamp')[:50])

    async def send_message_history(self):
        """Send message history to the client"""
        try:
            messages = await self.get_message_history()
            for message in messages:
                await self.chat_message({
                    'type': 'chat_message',
                    'message': message.content,
                    'sender_id': str(message.sender.id),
                    'sender_username': message.sender.username,
                    'timestamp': message.timestamp.isoformat(),
                    'message_id': str(message.id),
                })
        except Exception as e:
            logger.error(f"Error sending message history: {str(e)}")