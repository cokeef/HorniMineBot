from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext, StorageKey
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from config import ADMIN_IDS
from db import get_pending_applications, get_application_by_id, update_application, delete_application, get_application_media, get_user, get_open_tickets, get_ticket_by_id, add_ticket_message, close_ticket, assign_admin_to_ticket, get_open_tickets_by_user
import logging
from keyboards import get_admin_menu, get_application_action_keyboard, get_application_status_keyboard, get_main_menu, get_support_menu
from datetime import datetime
from .utils import translate_status, format_datetime, delete_messages, safe_message_delete, extract_id_from_callback, get_state_data, get_message_content_and_type, send_media_message
from .constants import *

support_router = Router()
logger = logging.getLogger(__name__)

# Фильтр для обработчиков поддержки (только для админов)
support_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
support_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

class CommentStates(StatesGroup):
    waiting_for_comment = State()

def translate_status(status: str) -> str:
    statuses = {
        "pending": "⏳ На рассмотрении",
        "approved": "✅ Одобрена",
        "rejected": "❌ Отклонена"
    }
    return statuses.get(status, status)

@support_router.callback_query(F.data == "view_applications")
async def view_applications(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        applications = await get_pending_applications()
        if not applications:
            await callback.message.answer(
                "📭 Нет заявок на рассмотрении.",
                reply_markup=get_admin_menu()
            )
        else:
            for app in applications:
                user = await get_user(app[1])
                username = f"@{user[1]}" if user and user[1] else f"ID {app[1]}"
                media = await get_application_media(app[0])
                media_count = len(media)
                await callback.message.answer(
                    f"📝 Заявка #{app[0]} от {username}:\n"
                    f"Статус: {translate_status(app[2])}\n"
                    f"📄 Описание: {app[3] or 'Отсутствует'}\n"
                    f"💬 Комментарий: {app[4] or 'Отсутствует'}\n"
                    f"📎 Файлов: {media_count}\n"
                    f"📅 Создано: {format_datetime(app[5])}\n"
                    f"✏️ Редактирований: {app[6] or 0}/3",
                    reply_markup=get_application_action_keyboard(app[0], app[2])
                )
    except Exception as e:
        logger.error(f"Ошибка в view_applications для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявок.")
    await callback.answer()

@support_router.callback_query(F.data.startswith("view_application_"))
async def view_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application_id = int(callback.data.split("_")[2])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            return
        user = await get_user(application[1])
        username = f"@{user[1]}" if user and user[1] else f"ID {application[1]}"
        media = await get_application_media(application[0])
        media_count = len(media)
        message = await callback.message.answer(
            f"📝 Заявка #{application[0]} от {username}:\n"
            f"Статус: {translate_status(application[2])}\n"
            f"📄 Описание: {application[3] or 'Отсутствует'}\n"
            f"💬 Комментарий: {application[4] or 'Отсутствует'}\n"
            f"📎 Файлов: {media_count}\n"
            f"📅 Создано: {format_datetime(application[5])}\n"
            f"✏️ Редактирований: {application[6] or 0}/3",
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
        await state.update_data(message_id=message.message_id, media_message_ids=media_message_ids)
    except Exception as e:
        logger.error(f"Ошибка в view_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявки.")
    await callback.answer()

@support_router.callback_query(F.data.startswith("approve_"))
async def approve_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application_id = int(callback.data.split("_")[1])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            return
        await update_application(application_id, application[3], application[6], "approved")
        user = await get_user(application[1])
        username = f"@{user[1]}" if user and user[1] else f"ID {application[1]}"
        await bot.send_message(
            application[1],
            f"✅ Ваша заявка #{application_id} одобрена!"
        )
        await callback.message.answer(
            f"✅ Заявка #{application_id} от {username} одобрена.",
            reply_markup=get_admin_menu()
        )
        logger.info(f"Заявка #{application_id} одобрена админом {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в approve_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при одобрении заявки.")
    await callback.answer()

@support_router.callback_query(F.data.startswith("reject_"))
async def reject_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application_id = int(callback.data.split("_")[1])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            return
        await update_application(application_id, application[3], application[6], "rejected")
        user = await get_user(application[1])
        username = f"@{user[1]}" if user and user[1] else f"ID {application[1]}"
        await bot.send_message(
            application[1],
            f"❌ Ваша заявка #{application_id} отклонена."
        )
        await callback.message.answer(
            f"❌ Заявка #{application_id} от {username} отклонена.",
            reply_markup=get_admin_menu()
        )
        logger.info(f"Заявка #{application_id} отклонена админом {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в reject_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при отклонении заявки.")
    await callback.answer()

@support_router.callback_query(F.data.startswith("comment_"))
async def comment_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application_id = int(callback.data.split("_")[1])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            return
        await state.set_state(CommentStates.waiting_for_comment)
        await state.update_data(application_id=application_id)
        await callback.message.answer(
            f"💬 Введите комментарий для заявки #{application_id}:",
            reply_markup=get_application_status_keyboard("view_applications")
        )
    except Exception as e:
        logger.error(f"Ошибка в comment_application для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при добавлении комментария.")
    await callback.answer()

@support_router.message(StateFilter(CommentStates.waiting_for_comment), F.text)
async def process_comment(message: Message, state: FSMContext, bot: Bot):
    try:
        data = await state.get_data()
        application_id = data.get("application_id")
        if not application_id:
            await message.answer("❌ Заявка не найдена.")
            await state.clear()
            return
        application = await get_application_by_id(application_id)
        if not application:
            await message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            await state.clear()
            return
        comment = message.text
        await update_application(application_id, application[3], application[6], application[2])
        user = await get_user(application[1])
        username = f"@{user[1]}" if user and user[1] else f"ID {application[1]}"
        await bot.send_message(
            application[1],
            f"💬 Новый комментарий к вашей заявке #{application_id}:\n{comment}"
        )
        await message.answer(
            f"💬 Комментарий к заявке #{application_id} от {username} добавлен.",
            reply_markup=get_admin_menu()
        )
        logger.info(f"Комментарий к заявке #{application_id} добавлен админом {message.from_user.id}")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в process_comment для админа {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при обработке комментария.")

@support_router.callback_query(F.data.startswith("delete_"))
async def delete_application_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application_id = int(callback.data.split("_")[1])
        application = await get_application_by_id(application_id)
        if not application:
            await callback.message.answer(
                "📭 Заявка не найдена.",
                reply_markup=get_admin_menu()
            )
            return
        await delete_application(application_id)
        user = await get_user(application[1])
        username = f"@{user[1]}" if user and user[1] else f"ID {application[1]}"
        await bot.send_message(
            application[1],
            f"🗑 Ваша заявка #{application_id} была удалена администратором."
        )
        await callback.message.answer(
            f"🗑 Заявка #{application_id} от {username} удалена.",
            reply_markup=get_admin_menu()
        )
        logger.info(f"Заявка #{application_id} удалена админом {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в delete_application_callback для админа {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при удалении заявки.")
    await callback.answer()

@support_router.callback_query()
async def unknown_callback_support(callback: CallbackQuery):
    """Обработчик всех необработанных callback-запросов в поддержке"""
    try:
        # Проверяем наличие админских префиксов и перенаправляем
        if callback.data.startswith("admin_chat_ticket_") or callback.data.startswith("admin_close_ticket_"):
            logger.info(f"Перенаправляем админский callback: {callback.data} в админский роутер")
            # Здесь не нужно ничего делать, callback будет перехвачен admin_router
            return
        elif callback.data.startswith("chat_ticket_"):
            # Преобразуем chat_ticket_X в admin_chat_ticket_X
            ticket_id = int(callback.data.split("_")[-1])
            new_callback_data = f"admin_chat_ticket_{ticket_id}"
            
            # Создаем новое событие с правильным callback_data
            from aiogram.types import CallbackQuery as CallbackQueryType
            
            # Заменяем data в callback
            callback_data = callback.model_dump()
            callback_data["data"] = new_callback_data
            new_callback = CallbackQueryType.model_validate(callback_data)
            
            logger.info(f"Преобразуем {callback.data} -> {new_callback_data}")
            
            # Импортируем обработчик из admin_router
            from .handlers_admin import admin_chat_ticket
            
            # Создаем объект FSMContext для передачи в обработчик
            from aiogram.fsm.storage.base import StorageKey
            from aiogram.fsm.context import FSMContext
            
            # Получаем текущее состояние
            state = FSMContext(
                bot=callback.bot,
                storage=callback.bot.fsm.storage,
                key=StorageKey(chat_id=callback.message.chat.id, user_id=callback.from_user.id, bot_id=callback.bot.id)
            )
            
            # Вызываем обработчик админского роутера
            await admin_chat_ticket(new_callback, state, callback.bot)
            return
        elif callback.data.startswith("view_ticket_"):
            # Преобразуем view_ticket_X в admin view_ticket_X
            ticket_id = int(callback.data.split("_")[-1])
            new_callback_data = f"view_ticket_{ticket_id}"
            
            # Создаем новое событие с правильным callback_data
            from aiogram.types import CallbackQuery as CallbackQueryType
            
            # Заменяем data в callback
            callback_data = callback.model_dump()
            callback_data["data"] = new_callback_data
            new_callback = CallbackQueryType.model_validate(callback_data)
            
            logger.info(f"Преобразуем {callback.data} -> {new_callback_data}")
            
            # Импортируем обработчик из admin_router
            from .handlers_admin import view_ticket
            
            # Создаем объект FSMContext для передачи в обработчик
            from aiogram.fsm.storage.base import StorageKey
            from aiogram.fsm.context import FSMContext
            
            # Получаем текущее состояние
            state = FSMContext(
                bot=callback.bot,
                storage=callback.bot.fsm.storage,
                key=StorageKey(chat_id=callback.message.chat.id, user_id=callback.from_user.id, bot_id=callback.bot.id)
            )
            
            # Вызываем обработчик админского роутера
            await view_ticket(new_callback, state, callback.bot)
            return
            
        logger.warning(f"Необработанный callback в support_router: {callback.data} от пользователя {callback.from_user.id}")
        await callback.answer(f"Эта функция пока не реализована")
    except Exception as e:
        logger.error(f"Ошибка в обработчике: {e}")
        await callback.answer("❌ Произошла ошибка")
    finally:
        await callback.answer()

@support_router.message()
async def unknown_message_support(message: Message, state: FSMContext):
    """Обработчик неизвестных сообщений"""
    current_state = await state.get_state()
    
    # Если админ отправил команду /start, обрабатываем ее специально
    if message.text and message.text.startswith('/start'):
        try:
            from .handlers_admin import admin_start
            await admin_start(message, state)
            return
        except Exception as e:
            logger.error(f"Ошибка при перенаправлении /start к admin_start: {e}")
    
    logger.warning(f"Необработанное сообщение от админа {message.from_user.id}, состояние: {current_state}")
    
    # Отвечаем только если админ не в особом состоянии
    if not current_state:
        await message.answer("🤔 Непонятная команда. Выберите действие:", reply_markup=get_admin_menu())