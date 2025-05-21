from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter, Command, CommandStart
from config import ADMIN_IDS
from db import get_pending_applications, get_application_by_id, update_application_status, get_application_media, get_open_tickets, delete_application, get_ticket_messages, update_application_comment, get_user, get_ticket_by_id, assign_admin_to_ticket, close_ticket, add_ticket_message, add_user
import logging
import aiosqlite
from keyboards import get_admin_menu, get_application_action_keyboard, get_main_menu, get_admin_ticket_keyboard
from aiogram.fsm.storage.base import StorageKey
from datetime import datetime
from .utils import translate_status, format_datetime, delete_messages, safe_message_delete, extract_id_from_callback, get_state_data, get_message_content_and_type, send_media_message
from .constants import *

admin_router = Router()

# Фильтры для админских команд уже установлены в __init__.py
# admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
# admin_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

logger = logging.getLogger(__name__)

class AdminCommentStates(StatesGroup):
    waiting_for_comment = State()

class AdminSupportStates(StatesGroup):
    chatting = State()

def translate_status(status: str) -> str:
    statuses = {
        "pending": "⏳ На рассмотрении",
        "approved": "✅ Одобрена",
        "rejected": "❌ Отклонена"
    }
    return statuses.get(status, status)

async def get_applications_by_status(status: str):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT application_id, user_id, status, description, comment, created_at, edit_count
            FROM applications
            WHERE status = ?
            ORDER BY created_at
        ''', (status,)) as cursor:
            return await cursor.fetchall()

@admin_router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    try:
        await callback.message.delete()
        await callback.message.answer(
            "⚙️ Админ-панель: выберите действие:",
            reply_markup=get_admin_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_menu для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка в админ-панели.")
    await callback.answer()

@admin_router.callback_query(F.data == "view_applications")
async def view_applications_admin(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        await callback.message.answer(
            "📬 Выберите категорию заявок:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏳ Ожидают", callback_data="view_pending")],
                [InlineKeyboardButton(text="✅ Одобренные", callback_data="view_approved")],
                [InlineKeyboardButton(text="❌ Отклонённые", callback_data="view_rejected")],
                [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Ошибка в view_applications_admin для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявок.")
    await callback.answer()

@admin_router.callback_query(F.data == "view_pending")
async def view_pending_applications(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        applications = await get_pending_applications()
        if not applications:
            await callback.message.answer(
                "📭 Нет заявок на рассмотрении.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")]
                ])
            )
        else:
            buttons = []
            for app in applications:
                user = await get_user(app[1])
                username = f"@{user[1]}" if user[1] else f"ID {app[1]}"
                buttons.append([InlineKeyboardButton(text=f"📝 Заявка #{app[0]} от {username}", callback_data=f"view_application_{app[0]}")])
            buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")])
            await callback.message.answer(
                "📬 Ожидающие заявки:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except Exception as e:
        logger.error(f"Ошибка в view_pending_applications для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявок.")
    await callback.answer()

@admin_router.callback_query(F.data == "view_approved")
async def view_approved_applications(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        applications = await get_applications_by_status('approved')
        if not applications:
            await callback.message.answer(
                "📭 Нет одобренных заявок.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")]
                ])
            )
        else:
            buttons = []
            for app in applications:
                user = await get_user(app[1])
                username = f"@{user[1]}" if user[1] else f"ID {app[1]}"
                buttons.append([InlineKeyboardButton(text=f"📝 Заявка #{app[0]} от {username}", callback_data=f"view_application_{app[0]}")])
            buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")])
            await callback.message.answer(
                "📬 Одобренные заявки:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except Exception as e:
        logger.error(f"Ошибка в view_approved_applications для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявок.")
    await callback.answer()

@admin_router.callback_query(F.data == "view_rejected")
async def view_rejected_applications(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        applications = await get_applications_by_status('rejected')
        if not applications:
            await callback.message.answer(
                "📭 Нет отклонённых заявок.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")]
                ])
            )
        else:
            buttons = []
            for app in applications:
                user = await get_user(app[1])
                username = f"@{user[1]}" if user[1] else f"ID {app[1]}"
                buttons.append([InlineKeyboardButton(text=f"📝 Заявка #{app[0]} от {username}", callback_data=f"view_application_{app[0]}")])
            buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="view_applications")])
            await callback.message.answer(
                "📬 Отклонённые заявки:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except Exception as e:
        logger.error(f"Ошибка в view_rejected_applications для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявок.")
    await callback.answer()

@admin_router.callback_query(F.data.startswith("view_application_"))
async def view_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        application_id = int(callback.data.split("_")[2])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
        else:
            user = await get_user(application[1])
            username = f"@{user[1]}" if user[1] else f"ID {application[1]}"
            media = await get_application_media(application[0])
            media_count = len(media)
            message = await callback.message.answer(
                f"📝 Заявка #{application[0]}:\n"
                f"👤 Пользователь: {username}\n"
                f"Статус: {translate_status(application[2])}\n"
                f"📄 Описание: {application[3] or 'Отсутствует'}\n"
                f"💬 Комментарий: {application[4] or 'Отсутствует'}\n"
                f"📎 Файлов: {media_count}\n"
                f"📅 Создано: {format_datetime(application[5])}",
                reply_markup=get_application_action_keyboard(application[0], application[2])
            )
            media_message_ids = []
            for item in media:
                try:
                    if item[3] == "photo":
                        media_message = await bot.send_photo(callback.from_user.id, item[2])
                    elif item[3] == "video":
                        media_message = await bot.send_video(callback.from_user.id, item[2])
                    elif item[3] == "document":
                        media_message = await bot.send_document(callback.from_user.id, item[2])
                    media_message_ids.append(media_message.message_id)
                except Exception as e:
                    logger.error(f"Ошибка отправки медиа {item[2]} админу {callback.from_user.id}: {e}")
                    await callback.message.answer("❌ Не удалось отправить одно из медиа.")
            await state.update_data(
                message_id=message.message_id,
                media_message_ids=media_message_ids
            )
    except Exception as e:
        logger.error(f"Ошибка в view_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявки.")
    await callback.answer()

@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_application(callback: CallbackQuery, bot: Bot):
    application_id = int(callback.data.split("_")[1])
    application = await get_application_by_id(application_id)
    
    if not application:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    
    # Получаем полные данные заявки
    full_data = await get_full_application_data(application_id)
    
    if not full_data:
        await callback.answer("Не удалось получить данные заявки", show_alert=True)
        return
    
    # Добавляем в вайтлист в зависимости от платформы
    if full_data['player_platform'] in ["java", "both"] and full_data['player_nickname_java']:
        success = await execute_whitelist_command(full_data['player_nickname_java'], "java")
        if not success:
            await callback.answer("Ошибка добавления в whitelist Java", show_alert=True)
            return
    
    if full_data['player_platform'] in ["bedrock", "both"] and full_data['player_nickname_bedrock']:
        success = await execute_whitelist_command(full_data['player_nickname_bedrock'], "bedrock")
        if not success:
            await callback.answer("Ошибка добавления в fwhitelist Bedrock", show_alert=True)
            return
    
    # Обновляем статус заявки
    await update_application_status(application_id, "approved", "")
    
    # Уведомляем пользователя
    await bot.send_message(
        application[1],
        "✅ Ваша заявка одобрена! Теперь вы можете зайти на сервер."
    )
    
    await callback.answer("Заявка одобрена", show_alert=True)
    await callback.message.edit_reply_markup(
        reply_markup=get_application_action_keyboard(application_id, "approved")
    )

@admin_router.callback_query(F.data.startswith("reject_"))
async def reject_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        data = await state.get_data()
        await delete_messages(bot, callback.from_user.id, [data.get("message_id")] + data.get("media_message_ids", []))
        application_id = int(callback.data.split("_")[1])
        application = await get_application_by_id(application_id)
        if application[2] != "pending":
            await callback.message.answer(
                f"📝 Заявка #{application_id} уже обработана ({translate_status(application[2])}).",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        await update_application_status(application_id, "rejected", application[4] or "❌ Отклонено администратором")
        user = await get_user(application[1])
        username = f"@{user[1]}" if user[1] else f"ID {application[1]}"
        try:
            await bot.send_message(
                application[1],
                f"❌ Ваша заявка #{application_id} отклонена."
            )
            logger.info(f"Уведомление об отклонении заявки #{application_id} отправлено пользователю {username}")
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {username}: {e}")
        await callback.message.answer(
            f"📝 Заявка #{application_id} от {username} отклонена.",
            reply_markup=get_admin_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в reject_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при отклонении заявки.")
    await callback.answer()

@admin_router.callback_query(F.data.startswith("comment_"))
async def comment_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        data = await state.get_data()
        await delete_messages(bot, callback.from_user.id, [data.get("message_id")] + data.get("media_message_ids", []))
        application_id = int(callback.data.split("_")[1])
        await state.update_data(application_id=application_id)
        message = await callback.message.answer(
            f"💬 Введите комментарий для заявки #{application_id}:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Отмена", callback_data="back_to_main")]
            ])
        )
        await state.update_data(message_id=message.message_id, media_message_ids=[])
        await state.set_state(AdminCommentStates.waiting_for_comment)
    except Exception as e:
        logger.error(f"Ошибка в comment_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при добавлении комментария.")
    await callback.answer()

@admin_router.message(StateFilter(AdminCommentStates.waiting_for_comment), F.text)
async def process_comment(message: Message, state: FSMContext, bot: Bot):
    try:
        comment = message.text
        data = await state.get_data()
        application_id = data.get("application_id")
        await delete_messages(bot, message.from_user.id, [data.get("message_id")])
        await update_application_comment(application_id, comment)
        application = await get_application_by_id(application_id)
        user = await get_user(application[1])
        username = f"@{user[1]}" if user[1] else f"ID {application[1]}"
        try:
            await bot.send_message(
                application[1],
                f"💬 Новый комментарий к вашей заявке #{application_id}:\n{comment}"
            )
            logger.info(f"Уведомление о комментарии к заявке #{application_id} отправлено пользователю {username}")
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя {username}: {e}")
        await message.answer(
            f"💬 Комментарий для заявки #{application_id} от {username} добавлен!",
            reply_markup=get_admin_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_comment для админа {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при сохранении комментария.")

@admin_router.callback_query(F.data.startswith("delete_"))
async def delete_application_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        data = await state.get_data()
        await delete_messages(bot, callback.from_user.id, [data.get("message_id")] + data.get("media_message_ids", []))
        application_id = int(callback.data.split("_")[1])
        user_id = await delete_application(application_id)
        if user_id:
            user = await get_user(user_id)
            username = f"@{user[1]}" if user[1] else f"ID {user_id}"
            try:
                await bot.send_message(
                    user_id,
                    f"🗑 Ваша заявка #{application_id} была удалена администратором."
                )
                logger.info(f"Уведомление об удалении заявки #{application_id} отправлено пользователю {username}")
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя {username}: {e}")
        await callback.message.answer(
            f"🗑 Заявка #{application_id} удалена!",
            reply_markup=get_admin_menu()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в delete_application_handler для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при удалении заявки.")
    await callback.answer()

@admin_router.callback_query(F.data == "view_tickets")
async def view_open_tickets(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        await callback.answer()
        return
    try:
        # Отвечаем на callback сразу, чтобы избежать ошибки с устаревшим запросом
        await callback.answer()
        
        await callback.message.delete()
        tickets = await get_open_tickets()
        if not tickets:
            await callback.message.answer(
                "📭 Нет активных вопросов.",
                reply_markup=get_admin_menu()
            )
        else:
            # Создаем список кнопок для активных вопросов
            buttons = []
            for ticket in tickets:
                # Пропускаем неактивные вопросы
                is_active = ticket[5] if len(ticket) > 5 else 0
                if is_active != 1:
                    continue
                
                # Получаем имя пользователя
                try:
                    user = await get_user(ticket[1])
                    username = f"@{user[1]}" if user and len(user) > 1 and user[1] else f"ID {ticket[1]}"
                except Exception as e:
                    logger.error(f"Ошибка получения данных пользователя {ticket[1]}: {e}")
                    username = f"ID {ticket[1]}"
                
                # Проверяем, назначен ли админ на вопрос
                admin_assigned = "✓" if ticket[3] else "✗"
                
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🆘 #{ticket[0]} от {username} | Админ: {admin_assigned}",
                        callback_data=f"view_ticket_{ticket[0]}"
                    )
                ])
            
            # Если после фильтрации активных вопросов список пуст
            if not buttons:
                await callback.message.answer(
                    "📭 Нет активных вопросов.",
                    reply_markup=get_admin_menu()
                )
                return
            
            # Добавляем кнопку "Назад"
            buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_menu")])
            
            # Отправляем сообщение со списком активных вопросов
            await callback.message.answer(
                "🆘 Активные вопросы:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
    except Exception as e:
        logger.error(f"Ошибка в view_open_tickets для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре вопросов.")
        # Чтобы гарантировать, что часики не зависнут, отвечаем еще раз, игнорируя ошибки
        try:
            await callback.answer()
        except Exception:
            pass

@admin_router.callback_query(F.data.startswith("view_ticket_"))
async def view_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.message.answer("🚫 Доступ к админ-панели запрещён!")
        return
    try:
        await callback.message.delete()
        ticket_id = int(callback.data.split("_")[2])
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await callback.message.answer(
                "📭 Вопрос не найден.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Получаем данные из кортежа с проверками
        user_id = ticket[1]
        admin_id = ticket[3] if len(ticket) > 3 else None
        created_at = ticket[4] if len(ticket) > 4 else None
        is_active = ticket[5] if len(ticket) > 5 else 0
            
        # Получаем информацию о пользователе
        user = await get_user(user_id)
        username = f"@{user[1]}" if user and len(user) > 1 and user[1] else f"ID {user_id}"
        
        # Информация о вопросе
        ticket_info = (
            f"🆘 Вопрос #{ticket_id} от {username}\n"
            f"📅 Создан: {format_datetime(created_at)}\n"
            f"Статус: {'🟢 Активен' if is_active == 1 else '🔴 Закрыт'}\n"
            f"👨‍💼 Обрабатывает: {admin_id or 'Нет'}"
        )
        
        # Создаем клавиатуру с кнопками в зависимости от статуса вопроса
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        if is_active == 1:
            keyboard = get_admin_ticket_keyboard(ticket_id)
        else:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="↩️ Назад", callback_data="view_tickets")
            ])
        
        # Отправляем информацию о вопросе
        message = await callback.message.answer(ticket_info, reply_markup=keyboard)
        
        # Получаем сообщения в вопросе
        messages = await get_ticket_messages(ticket_id)
        
        # Отправляем сообщения вопроса
        media_message_ids = []
        
        if not messages:
            info_msg = await callback.message.answer("📭 В этом вопросе еще нет сообщений.")
            media_message_ids.append(info_msg.message_id)
        else:
            # Сначала отправляем заголовок с историей сообщений
            history_header = await callback.message.answer("📝 История сообщений:")
            media_message_ids.append(history_header.message_id)
            
            # Отправляем первые 10 сообщений вопроса
            count = 0
            for msg in messages:
                if count >= 10:  # Ограничиваем количество показываемых сообщений
                    break
                
                try:
                    # Подготавливаем данные сообщения
                    msg_id = msg[0] 
                    msg_type = msg[3] if len(msg) > 3 else "text"
                    msg_content = msg[4] if len(msg) > 4 else ""
                    msg_time = format_datetime(msg[5]) if len(msg) > 5 else "неизвестно"
                    msg_sender_type = msg[6] if len(msg) > 6 else "user"
                    msg_username = msg[7] if len(msg) > 7 else "неизвестно"
                    
                    # Формируем заголовок сообщения
                    sender_prefix = "👤" if msg_sender_type == "user" else "👨‍💼"
                    sender_name = f"{sender_prefix} {msg_username}"
                    
                    # Отправляем сообщение в зависимости от типа
                    if msg_type == "text":
                        msg_text = f"{sender_name} ({msg_time}):\n{msg_content}"
                        media_msg = await callback.message.answer(msg_text)
                        media_message_ids.append(media_msg.message_id)
                    elif msg_type == "sticker":
                        # Отправляем стикер
                        sticker_msg = await bot.send_sticker(callback.from_user.id, msg_content)
                        media_message_ids.append(sticker_msg.message_id)
                        
                        # Отправляем информацию о стикере
                        info_msg = await callback.message.answer(f"{sender_name} отправил стикер ({msg_time})")
                        media_message_ids.append(info_msg.message_id)
                    else:
                        # Для медиафайлов - добавляем подпись с информацией
                        caption = f"{sender_name} ({msg_time})"
                        
                        if msg_type == "photo":
                            media_msg = await bot.send_photo(callback.from_user.id, msg_content, caption=caption)
                        elif msg_type == "video":
                            media_msg = await bot.send_video(callback.from_user.id, msg_content, caption=caption)
                        elif msg_type == "document":
                            media_msg = await bot.send_document(callback.from_user.id, msg_content, caption=caption)
                        else:
                            # Неизвестный тип - отправляем только информацию
                            media_msg = await callback.message.answer(f"{sender_name} отправил медиафайл ({msg_time})")
                        
                        media_message_ids.append(media_msg.message_id)
                except Exception as e:
                    logger.error(f"Ошибка при отображении сообщения {msg[0] if len(msg) > 0 else 'unknown'}: {e}")
                
                count += 1
                
            # Если сообщений больше 10, добавляем информацию об этом
            if len(messages) > 10:
                more_msg = await callback.message.answer(f"... и еще {len(messages) - 10} сообщений. Перейдите в чат для просмотра всей истории.")
                media_message_ids.append(more_msg.message_id)
        
        # Сохраняем ID сообщений для возможности удаления
        await state.update_data(message_id=message.message_id, media_message_ids=media_message_ids)
        
    except Exception as e:
        logger.error(f"Ошибка в view_ticket для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре вопроса в поддержку.")
    await callback.answer()

@admin_router.callback_query()
async def handle_admin_callbacks(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обрабатывает все админские callback запросы, которые не обработаны другими хендлерами"""
    try:
        # Обработка callback для вопросов поддержки (чат)
        if callback.data.startswith("admin_chat_ticket_"):
            ticket_id = int(callback.data.split("_")[-1])
            logger.info(f"Перенаправляю запрос admin_chat_ticket_{ticket_id} на admin_chat_ticket")
            return await admin_chat_ticket(callback, state, bot)
        
        # Обработка callback для закрытия вопросов поддержки
        elif callback.data.startswith("admin_close_ticket_"):
            ticket_id = int(callback.data.split("_")[-1])
            logger.info(f"Перенаправляю запрос admin_close_ticket_{ticket_id} на admin_close_ticket")
            return await admin_close_ticket(callback, state, bot)
        
        # Обычные правила обработки для других callback
        elif callback.data == "back_to_main":
            await callback.message.delete()
            await callback.message.answer(
                "⚙️ Админ-панель: выберите действие:",
                reply_markup=get_admin_menu()
            )
        elif callback.data == "view_tickets":
            # Обработка просмотра списка тикетов
            logger.info(f"Админ {callback.from_user.id} переходит к списку вопросов")
            await view_open_tickets(callback)
        elif callback.data == "view_applications":
            # Обработка просмотра списка заявок
            logger.info(f"Админ {callback.from_user.id} переходит к списку заявок")
            await view_applications_admin(callback)
        else:
            # Стандартная обработка неизвестных callback
            logger.warning(f"Неизвестный callback: {callback.data} от админа {callback.from_user.id}")
            await callback.answer("Эта функция пока не реализована. Выберите другое действие.")
            await callback.message.answer("Выберите действие:", reply_markup=get_admin_menu())
    
    except Exception as e:
        logger.error(f"Ошибка при обработке callback {callback.data}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при обработке запроса.",
            reply_markup=get_admin_menu()
        )
    
    # Всегда отвечаем на callback
    await callback.answer()

@admin_router.message()
async def all_admin_messages(message: Message, state: FSMContext, bot: Bot):
    """Обработчик всех сообщений админа"""
    # Получаем текущее состояние и сравниваем его строковое представление
    current_state = await state.get_state()
    logger.info(f"Админ {message.from_user.id} отправил сообщение: '{message.text}', состояние: {current_state}")
    
    # Если админ находится в состоянии чата, обрабатываем сообщение как сообщение в чате
    if current_state == "AdminSupportStates:chatting":
        # Получаем данные из состояния
        data = await state.get_data()
        logger.info(f"Данные состояния админа в чате: {data}")
        
        ticket_id = data.get("ticket_id")
        user_id = data.get("user_id")
        
        logger.info(f"Админ {message.from_user.id} отправляет сообщение в тикет #{ticket_id} пользователю {user_id}")
        
        # Проверяем наличие необходимых данных
        if not ticket_id or not user_id:
            logger.error(f"Отсутствуют данные о тикете в состоянии: {data}")
            await message.answer(
                "❌ Произошла ошибка: данные о вопросе не найдены.",
                reply_markup=get_admin_menu()
            )
            await state.clear()
            return
        
        # Получаем информацию о вопросе
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await message.answer(
                "❌ Вопрос не найден в базе данных.",
                reply_markup=get_admin_menu()
            )
            await state.clear()
            return
        
        # Проверяем, активен ли вопрос
        is_active = ticket[5] if len(ticket) > 5 else 0
        if is_active == 0:
            await message.answer(
                "❌ Вопрос закрыт и недоступен для общения.",
                reply_markup=get_admin_menu()
            )
            await state.clear()
            return
        
        # Получаем содержимое и тип сообщения
        content, message_type = get_message_content_and_type(message)
        logger.info(f"Сообщение админа имеет тип {message_type} и содержимое: {content[:50]}...")
        
        # Проверяем, поддерживается ли тип сообщения
        if message_type == "unknown":
            await message.answer("❌ Неподдерживаемый тип сообщения. Отправьте текст, фото, видео, документ или стикер.")
            return
        
        # Сохраняем сообщение в базе данных
        await add_ticket_message(ticket_id, message.from_user.id, message.message_id, message_type, content, "admin")
        
        # Формируем и отправляем сообщение пользователю
        try:
            # Отправляем в зависимости от типа
            if message_type == "text":
                await bot.send_message(
                    user_id,
                    f"💬 Ответ от поддержки по вопросу #{ticket_id}:\n{content}"
                )
            elif message_type == "sticker":
                await bot.send_sticker(user_id, content)
                # Дополнительное текстовое сообщение для контекста
                await bot.send_message(
                    user_id, 
                    f"👨‍💼 Сообщение от поддержки по вопросу #{ticket_id}"
                )
            else:
                # Для фото, видео, документов
                caption = f"💬 Ответ от поддержки по вопросу #{ticket_id}"
                if message.caption:
                    caption += f"\n{message.caption}"
                
                if message_type == "photo":
                    await bot.send_photo(user_id, content, caption=caption)
                elif message_type == "video":
                    await bot.send_video(user_id, content, caption=caption)
                elif message_type == "document":
                    await bot.send_document(user_id, content, caption=caption)
                    
            # Подтверждение отправки для админа
            conf_message = await message.answer(
                "✅ Сообщение отправлено пользователю!",
                reply_markup=get_admin_ticket_keyboard(ticket_id, in_chat=True)
            )
            
            # Сохраняем ID предыдущего сообщения с подтверждением для возможного удаления
            prev_conf_id = data.get("confirmation_message_id")
            if prev_conf_id:
                try:
                    await bot.delete_message(message.from_user.id, prev_conf_id)
                except Exception as e:
                    logger.warning(f"Не удалось удалить предыдущее подтверждение: {e}")
            
            # Обновляем данные состояния, сохраняя ID нового сообщения подтверждения
            await state.update_data(confirmation_message_id=conf_message.message_id)
            
            logger.info(f"Сообщение от админа {message.from_user.id} отправлено пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
            await message.answer(
                "❌ Не удалось отправить сообщение пользователю. Возможно, он заблокировал бота.",
                reply_markup=get_admin_ticket_keyboard(ticket_id, in_chat=True)
            )
            
        return
    
    # Если админ отправил команду /start, обрабатываем ее специально
    if message.text and message.text.startswith('/start'):
        try:
            await state.clear()
            await add_user(message.from_user.id, message.from_user.username or str(message.from_user.id))
            await message.answer(
                "👋 Добро пожаловать в админ-панель HorniMineBot!\n"
                "Выберите действие в меню ниже:",
                reply_markup=get_admin_menu()
            )
            logger.info(f"Админ {message.from_user.id} использовал команду /start")
            return
        except Exception as e:
            logger.error(f"Ошибка при обработке команды /start для админа {message.from_user.id}: {e}")
    
    # Для остальных сообщений
    logger.warning(f"Необработанное сообщение от админа {message.from_user.id}, состояние: {current_state}")
    
    # Если админ не в особом состоянии, предлагаем выбрать действие
    if not current_state:
        await message.answer(
            "🤔 Непонятная команда. Выберите действие в панели администратора:",
            reply_markup=get_admin_menu()
        )

@admin_router.message(CommandStart())
async def admin_start(message: Message, state: FSMContext):
    """Обработчик команды /start для админов"""
    try:
        await state.clear()
        await add_user(message.from_user.id, message.from_user.username or str(message.from_user.id))
        await message.answer(
            "👋 Добро пожаловать в админ-панель HorniMineBot!\n"
            "Выберите действие в меню ниже:",
            reply_markup=get_admin_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка в admin_start для админа {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова позже.")

@admin_router.callback_query(F.data.startswith("admin_chat_ticket_"))
async def admin_chat_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для входа админа в чат с пользователем"""
    try:
        # Извлекаем ID вопроса
        ticket_id = int(callback.data.split("_")[-1])
        logger.info(f"Админ {callback.from_user.id} входит в чат по вопросу #{ticket_id}")
        
        # Удаляем сообщение с кнопкой
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
            
        # Очищаем предыдущие данные состояния
        data = await state.get_data()
        message_id = data.get("message_id")
        media_message_ids = data.get("media_message_ids", [])
        
        # Удаляем предыдущие сообщения если они есть
        if message_id or media_message_ids:
            await delete_messages(bot, callback.from_user.id, [message_id] + media_message_ids if message_id else media_message_ids)
        
        # Очищаем текущее состояние, чтобы избежать конфликтов
        await state.clear()
        
        # Получаем информацию о вопросе
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await callback.message.answer(
                "❌ Вопрос не найден.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Проверяем активность вопроса
        is_active = ticket[5] if len(ticket) > 5 else 0
        if is_active == 0:
            await callback.message.answer(
                "❌ Вопрос закрыт и недоступен для общения.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Назначаем админа на вопрос
        user_id = ticket[1]
        await assign_admin_to_ticket(ticket_id, callback.from_user.id)
        
        # Получаем информацию о пользователе
        user = await get_user(user_id)
        username = f"@{user[1]}" if user and user[1] else f"ID {user_id}"
        
        # Отправляем сообщение о входе в чат
        message = await callback.message.answer(
            f"💬 Вы в чате с {username} (вопрос #{ticket_id}).\n"
            f"Отправляйте сообщения для ответа пользователю:",
            reply_markup=get_admin_ticket_keyboard(ticket_id, in_chat=True)
        )
        
        # Сохраняем информацию о чате в состоянии
        await state.set_state(AdminSupportStates.chatting)
        await state.update_data(
            ticket_id=ticket_id,
            user_id=user_id,  # Важно! Сохраняем ID пользователя
            message_id=message.message_id,
            media_message_ids=[]
        )
        
        # Логируем сохраненные данные для отладки
        logger.info(f"Сохранены данные в состоянии админа: ticket_id={ticket_id}, user_id={user_id}")
        
        # Загружаем последние сообщения (максимум 5)
        messages = await get_ticket_messages(ticket_id)
        if messages:
            # Отображаем только последние 5 сообщений для чистоты интерфейса
            last_messages = messages[-5:] if len(messages) > 5 else messages
            media_message_ids = []
            
            # Заголовок истории
            history_header = await callback.message.answer("📝 Последние сообщения:")
            media_message_ids.append(history_header.message_id)
            
            # Отображаем сообщения
            for msg in last_messages:
                try:
                    msg_type = msg[3] if len(msg) > 3 else "text"
                    msg_content = msg[4] if len(msg) > 4 else ""
                    msg_time = format_datetime(msg[5]) if len(msg) > 5 else "неизвестно"
                    msg_sender_type = msg[6] if len(msg) > 6 else "user"
                    msg_username = msg[7] if len(msg) > 7 else "неизвестно"
                    
                    sender_prefix = "👤" if msg_sender_type == "user" else "👨‍💼"
                    sender_name = f"{sender_prefix} {msg_username}"
                    
                    if msg_type == "text":
                        msg_text = f"{sender_name} ({msg_time}):\n{msg_content}"
                        history_msg = await callback.message.answer(msg_text)
                        media_message_ids.append(history_msg.message_id)
                    elif msg_type in ["photo", "video", "document", "sticker"]:
                        # Отправляем медиафайл с подписью
                        caption = f"{sender_name} ({msg_time})"
                        media_msg = await send_media_message(bot, callback.from_user.id, msg_type, msg_content, caption)
                        if media_msg:
                            media_message_ids.append(media_msg.message_id)
                except Exception as e:
                    logger.error(f"Ошибка при отображении истории сообщений: {e}")
            
            # Разделитель между историей и новыми сообщениями
            separator = await callback.message.answer("➖➖➖➖➖➖➖➖➖➖➖➖")
            media_message_ids.append(separator.message_id)
            
            # Обновляем список ID медиасообщений в состоянии
            await state.update_data(media_message_ids=media_message_ids)
        
        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                user_id,
                f"👨‍💼 Администратор подключился к чату по вашему вопросу #{ticket_id}."
            )
            logger.info(f"Отправлено уведомление пользователю {user_id} о входе админа в чат")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_chat_ticket для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при входе в чат поддержки.")
        await callback.answer()

@admin_router.callback_query(F.data.startswith("admin_close_ticket_"))
async def admin_close_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для закрытия тикета администратором"""
    try:
        # Извлекаем ID вопроса
        ticket_id = int(callback.data.split("_")[-1])
        logger.info(f"Админ {callback.from_user.id} закрывает вопрос #{ticket_id}")
        
        # Удаляем сообщение с кнопкой
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
        
        # Получаем информацию о вопросе
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await callback.message.answer(
                "❌ Вопрос не найден.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Проверяем, активен ли вопрос
        ticket_status = ticket[2] if len(ticket) > 2 else STATUS_CLOSED
        if ticket_status == STATUS_CLOSED:
            await callback.message.answer(
                "❌ Вопрос уже закрыт.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Получаем данные пользователя
        user_id = ticket[1]
        user = await get_user(user_id)
        username = f"@{user[1]}" if user and user[1] else f"ID {user_id}"
        
        # Закрываем вопрос
        success = await close_ticket(ticket_id)
        if not success:
            await callback.message.answer(
                "❌ Не удалось закрыть вопрос. Попробуйте позже.",
                reply_markup=get_admin_menu()
            )
            await callback.answer()
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        current_state = await state.get_state()
        
        # Удаляем предыдущие сообщения, если админ в чате
        if current_state == AdminSupportStates.chatting.__str__():
            message_id = data.get("message_id")
            media_message_ids = data.get("media_message_ids", [])
            
            if message_id or media_message_ids:
                await delete_messages(bot, callback.from_user.id, [message_id] + media_message_ids if message_id else media_message_ids)
        
        # Очищаем состояние админа
        await state.clear()
        
        # Уведомляем пользователя о закрытии вопроса
        try:
            await bot.send_message(
                user_id,
                f"✅ Администратор закрыл ваш вопрос #{ticket_id}."
            )
            logger.info(f"Отправлено уведомление пользователю {user_id} о закрытии вопроса")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        # Отправляем подтверждение админу
        await callback.message.answer(
            f"✅ Вопрос #{ticket_id} от {username} закрыт.",
            reply_markup=get_admin_menu()
        )
        
        logger.info(f"Вопрос #{ticket_id} закрыт админом {callback.from_user.id}")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_close_ticket для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при закрытии вопроса.")
        await callback.answer()

@admin_router.callback_query(F.data == "view_tickets")
async def back_to_tickets_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик для возврата к списку вопросов из чата"""
    try:
        logger.info(f"Админ {callback.from_user.id} возвращается к списку вопросов")
        
        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
        
        # Получаем данные из состояния
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        message_id = data.get("message_id")
        media_message_ids = data.get("media_message_ids", [])
        
        # Удаляем все сообщения чата
        if message_id or media_message_ids:
            await delete_messages(bot, callback.from_user.id, [message_id] + media_message_ids if message_id else media_message_ids)
        
        # Очищаем состояние
        await state.clear()
        
        # Вызываем обработчик просмотра списка открытых вопросов
        await view_open_tickets(callback)
        
        # Если был активный тикет, логируем информацию
        if ticket_id:
            logger.info(f"Админ {callback.from_user.id} вышел из чата вопроса #{ticket_id}")
    
    except Exception as e:
        logger.error(f"Ошибка в back_to_tickets_list для админа {callback.from_user.id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при возврате к списку вопросов.",
            reply_markup=get_admin_menu()
        )
        await callback.answer()