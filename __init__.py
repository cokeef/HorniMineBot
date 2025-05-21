"""Инициализация обработчиков бота"""

from .handlers_user import user_router
from .handlers_admin import admin_router
from .handlers_support import support_router
from aiogram import F
from config import ADMIN_IDS
from .utils import (
    translate_status,
    format_datetime,
    delete_messages,
    safe_message_delete,
    extract_id_from_callback,
    get_state_data,
    get_message_content_and_type,
    send_media_message
)
from .constants import *

# Порядок роутеров важен! 
# Сначала админские команды, затем поддержка, и в конце - пользовательские

# Устанавливаем высокий приоритет для admin_router для обработки админских запросов
admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

# Роутер поддержки действует только для админов и требует правильного префикса в callback
# Важно: не должен конфликтовать с админским роутером по callback-данным
support_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
support_router.callback_query.filter(
    F.from_user.id.in_(ADMIN_IDS) & 
    ~F.data.startswith("admin_")  # Исключаем admin_ префиксы, их обрабатывает admin_router
)

# Пользовательский роутер обрабатывает все, что не относится к админам
# Исключения составляют команды /start и /help, которые обрабатываются для всех
# Это обеспечивается соответствующими фильтрами в handlers_user.py

routers = [admin_router, support_router, user_router]

__all__ = [
    'routers',
    'user_router',
    'admin_router',
    'support_router',
    'translate_status',
    'format_datetime',
    'delete_messages',
    'safe_message_delete',
    'extract_id_from_callback',
    'get_state_data',
    'get_message_content_and_type',
    'send_media_message'
]