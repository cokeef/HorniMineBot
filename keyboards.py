from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db import get_application_by_user_id, get_open_tickets_by_user

async def get_main_menu(is_admin: bool, user_id: int) -> InlineKeyboardMarkup:
    if is_admin:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📬 Заявки", callback_data="view_applications")],
            [InlineKeyboardButton(text="🆘 Активные вопросы", callback_data="view_tickets")]
        ])
    application = await get_application_by_user_id(user_id)
    buttons = []
    if application:
        buttons.append([InlineKeyboardButton(text="📋 Моя заявка", callback_data="view_application")])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Подать заявку", callback_data="create_application")])
    buttons.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="create_ticket")])
    buttons.append([InlineKeyboardButton(text="ℹ️ О сервере", callback_data="about_server")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📬 Заявки", callback_data="view_applications")],
        [InlineKeyboardButton(text="🆘 Активные вопросы", callback_data="view_tickets")]
    ])

async def get_application_menu(status: str, edit_count: int) -> InlineKeyboardMarkup:
    buttons = []
    if status == "pending" and edit_count < 3:
        buttons.append([InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_application")])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_application_action_keyboard(application_id: int, status: str) -> InlineKeyboardMarkup:
    buttons = []
    if status == "pending":
        buttons.extend([
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{application_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{application_id}")],
            [InlineKeyboardButton(text="💬 Добавить комментарий", callback_data=f"comment_{application_id}")]
        ])
    buttons.extend([
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_{application_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_application_status_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Отмена", callback_data=action)]
    ])

async def get_application_description_keyboard(is_edit: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_edit:
        buttons.append([InlineKeyboardButton(text="📝 Оставить прежнее описание", callback_data="keep_description")])
    buttons.append([InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def get_application_media_keyboard(is_edit: bool) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✅ Готово", callback_data="finish_application")],
    ]
    if is_edit:
        buttons.append([InlineKeyboardButton(text="📎 Оставить прежние медиа", callback_data="keep_media")])
    buttons.append([InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_ticket_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для пользователя в чате тикета"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Выйти из чата", callback_data="exit_chat")],
        [InlineKeyboardButton(text="✅ Закрыть вопрос", callback_data="close_user_ticket")]
    ])

def get_user_tickets_menu(tickets: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🆘 Вопрос #{ticket[0]}", callback_data=f"view_my_ticket_{ticket[0]}")]
        for ticket in tickets
    ]
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="create_ticket")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

def get_support_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Задать новый вопрос", callback_data="new_ticket")],
        [InlineKeyboardButton(text="📋 Мои активные вопросы", callback_data="view_my_tickets")],
        [InlineKeyboardButton(text="↩️ Вернуться в меню", callback_data="back_to_main")]
    ])

def get_admin_ticket_keyboard(ticket_id: int, in_chat: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопками для действий с тикетом"""
    buttons = []
    
    if not in_chat:
        buttons.append([InlineKeyboardButton(text="💬 Перейти в чат с пользователем", callback_data=f"admin_chat_ticket_{ticket_id}")])
    
    buttons.append([InlineKeyboardButton(text="✅ Закрыть вопрос", callback_data=f"admin_close_ticket_{ticket_id}")])
    
    if in_chat:
        buttons.append([InlineKeyboardButton(text="↩️ Вернуться к списку вопросов", callback_data="view_tickets")])
    else:
        buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="view_tickets")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_platform_choice_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора платформы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Java", callback_data="platform_java")],
        [InlineKeyboardButton(text="Bedrock", callback_data="platform_bedrock")],
        [InlineKeyboardButton(text="Обе платформы", callback_data="platform_both")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_previous_step")]
    ])

def get_back_button_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура только с кнопкой назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_previous_step")]
    ])

def get_accept_policy_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для принятия политики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="accept_policy")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

def get_skip_or_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопками пропустить и назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_step")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_previous_step")]
    ])

def get_media_continue_keyboard(media_type: str, current_count: int, max_count: int) -> InlineKeyboardMarkup:
    """Клавиатура для добавления медиафайлов с текущим счетчиком"""
    buttons = []
    if current_count >= max_count:
        buttons.append([InlineKeyboardButton(text="✅ Продолжить", callback_data=f"continue_from_{media_type}")])
    else:
        buttons.append([InlineKeyboardButton(text=f"✅ Продолжить ({current_count}/{max_count})", callback_data=f"continue_from_{media_type}")])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_previous_step")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_application_review_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра и отправки заявки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="send_application")],
        [InlineKeyboardButton(text="↩️ Редактировать", callback_data="edit_application_form")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_application")]
    ])