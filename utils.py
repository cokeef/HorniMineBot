from aiogram import Bot
from datetime import datetime
import logging
from typing import List, Optional, Tuple, Union
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

def translate_status(status: str) -> str:
    """Переводит статусы на русский язык"""
    statuses = {
        "pending": "⏳ На рассмотрении",
        "approved": "✅ Одобрена",
        "rejected": "❌ Отклонена",
        "open": "🟢 Активен",
        "closed": "🔴 Закрыт"
    }
    return statuses.get(status, status)

def format_datetime(timestamp) -> str:
    """Форматирует временную метку в читаемый формат"""
    try:
        return datetime.fromisoformat(str(timestamp)).strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка форматирования времени {timestamp}: {e}")
        return str(timestamp)

async def delete_messages(bot: Bot, user_id: int, message_ids: List[Optional[int]]) -> None:
    """Безопасно удаляет сообщения"""
    if not message_ids:
        return
    
    for msg_id in message_ids:
        if not msg_id:
            continue
        try:
            await bot.delete_message(user_id, msg_id)
        except Exception as e:
            # Игнорируем ошибки для уже удаленных сообщений
            if "message to delete not found" in str(e) or "message can't be deleted" in str(e):
                pass
            else:
                logger.warning(f"Не удалось удалить сообщение {msg_id}: {e}")

async def safe_message_delete(message: Message) -> None:
    """Безопасно удаляет одно сообщение"""
    try:
        await message.delete()
    except Exception as e:
        # Игнорируем ошибки для уже удаленных сообщений
        if "message to delete not found" in str(e) or "message can't be deleted" in str(e):
            pass
        else:
            logger.warning(f"Не удалось удалить сообщение: {e}")

async def extract_id_from_callback(callback: CallbackQuery, prefix: str) -> Optional[int]:
    """Безопасно извлекает ID из callback данных"""
    try:
        return int(callback.data.split(f"{prefix}_")[1])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка извлечения ID из callback {callback.data}: {e}")
        return None

async def get_state_data(state: FSMContext, keys: List[str]) -> Tuple[Union[int, str, None], ...]:
    """Безопасно получает данные из состояния"""
    data = await state.get_data()
    return tuple(data.get(key) for key in keys)

def get_message_content_and_type(message):
    """Получает содержимое и тип сообщения"""
    content = message.text or message.caption or ""
    message_type = "unknown"
    
    if message.text:
        message_type = "text"
    elif message.photo:
        content = message.photo[-1].file_id
        message_type = "photo"
    elif message.video:
        content = message.video.file_id
        message_type = "video"
    elif message.document:
        content = message.document.file_id
        message_type = "document"
    elif message.sticker:
        content = message.sticker.file_id
        message_type = "sticker"
    
    return content, message_type

async def send_media_message(bot, chat_id, message_type, content, caption=None):
    """Отправляет медиа-сообщение на основе его типа"""
    try:
        if message_type == "text":
            return await bot.send_message(chat_id, content)
        elif message_type == "photo":
            return await bot.send_photo(chat_id, content, caption=caption)
        elif message_type == "video":
            return await bot.send_video(chat_id, content, caption=caption)
        elif message_type == "document":
            return await bot.send_document(chat_id, content, caption=caption)
        elif message_type == "sticker":
            return await bot.send_sticker(chat_id, content)
        else:
            # Для неизвестных типов просто отправляем текстовое сообщение
            logger.warning(f"Неподдерживаемый тип сообщения: {message_type}")
            return await bot.send_message(chat_id, "Неподдерживаемый тип медиа")
    except Exception as e:
        logger.error(f"Ошибка отправки медиа {message_type} пользователю {chat_id}: {e}")
        return None 