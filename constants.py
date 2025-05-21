"""Константы для обработчиков бота"""

# Статусы заявок
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

# Статусы тикетов
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"

# Типы отправителей
SENDER_USER = "user"
SENDER_ADMIN = "admin"

# Типы медиа
MEDIA_TEXT = "text"
MEDIA_PHOTO = "photo"
MEDIA_VIDEO = "video"
MEDIA_DOCUMENT = "document"
MEDIA_STICKER = "sticker"
MEDIA_UNKNOWN = "unknown"

# Максимальное количество редактирований заявки
MAX_EDIT_COUNT = 3

# Префиксы callback-данных
CALLBACK_VIEW_APPLICATION = "view_application"
CALLBACK_APPROVE = "approve"
CALLBACK_REJECT = "reject"
CALLBACK_COMMENT = "comment"
CALLBACK_DELETE = "delete"
CALLBACK_CHAT_TICKET = "chat_ticket"
CALLBACK_CLOSE_TICKET = "close_ticket"
CALLBACK_VIEW_TICKET = "view_ticket"

# Сообщения
MSG_NO_RIGHTS = "🚫 У вас нет прав для выполнения этого действия"
MSG_ERROR = "❌ Произошла ошибка. Попробуйте позже"
MSG_NOT_FOUND = "📭 Не найдено"
MSG_SUCCESS = "✅ Успешно выполнено"
MSG_UNKNOWN_COMMAND = "🤔 Неизвестная команда"

# Эмодзи
EMOJI_PENDING = "⏳"
EMOJI_APPROVED = "✅"
EMOJI_REJECTED = "❌"
EMOJI_OPEN = "🟢"
EMOJI_CLOSED = "🔴"
EMOJI_ERROR = "❌"
EMOJI_SUCCESS = "✅"
EMOJI_WARNING = "⚠️"
EMOJI_INFO = "ℹ️"
EMOJI_QUESTION = "❓"
EMOJI_BACK = "↩️"
EMOJI_EDIT = "✏️"
EMOJI_DELETE = "🗑"
EMOJI_CHAT = "💬"
EMOJI_SUPPORT = "🆘"
EMOJI_ADMIN = "👨‍💼"
EMOJI_USER = "👤"
EMOJI_FILE = "📎"
EMOJI_CALENDAR = "📅"
EMOJI_DESCRIPTION = "📄"
EMOJI_COMMENT = "💬" 