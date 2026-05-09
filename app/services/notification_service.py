"""
Notification Service
Gửi thông báo realtime cho user qua WebSocket (notification channel riêng).
Các event: new_match, new_message, new_reaction, new_comment.
"""

from app.core.connection_manager import manager


async def notify_new_match(recipient_id: str, match_data: dict):
    await manager.send_notification(recipient_id, {
        "type": "new_match",
        "match": match_data,
    })


async def notify_new_message(recipient_id: str, message_data: dict, from_username: str):
    await manager.send_notification(recipient_id, {
        "type": "new_message",
        "from_username": from_username,
        "message": message_data,
    })


async def notify_new_reaction(recipient_id: str, post_id: str, from_username: str, reaction_type: str):
    await manager.send_notification(recipient_id, {
        "type": "new_reaction",
        "post_id": post_id,
        "from_username": from_username,
        "reaction_type": reaction_type,
    })


async def notify_new_comment(recipient_id: str, post_id: str, from_username: str, preview: str):
    await manager.send_notification(recipient_id, {
        "type": "new_comment",
        "post_id": post_id,
        "from_username": from_username,
        "preview": preview[:80],
    })
