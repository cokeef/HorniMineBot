from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.storage.base import StorageKey
from config import ADMIN_IDS
from db import add_user, get_application_by_user_id, add_application, update_application, add_application_media, get_application_media, add_ticket, add_ticket_message, close_ticket, get_ticket_by_id, get_user, get_open_tickets_by_user, delete_application_media, update_application_field, add_application_with_platform, add_skin_media, add_project_media, get_application_media_by_category
import aiosqlite
import logging
from keyboards import get_main_menu, get_application_menu, get_user_ticket_keyboard, get_user_tickets_menu, get_back_button, get_support_menu, get_application_description_keyboard, get_application_media_keyboard, get_admin_menu, get_accept_policy_keyboard, get_back_button_keyboard
from datetime import datetime
from .utils import format_datetime, delete_messages, safe_message_delete, extract_id_from_callback, get_state_data, get_message_content_and_type, send_media_message
from .constants import *
from aiogram.utils.media_group import MediaGroupBuilder
from .handlers_admin import admin_chat_ticket, view_ticket, admin_start

user_router = Router()
logger = logging.getLogger(__name__)

# Для команды /start исключаем фильтрацию, чтобы она работала для всех пользователей
# Для остальных команд фильтруем, чтобы они обрабатывались только для обычных пользователей
user_router.message.filter(
    lambda message: (
        not message.from_user.id in ADMIN_IDS or 
        (isinstance(message, Message) and message.text and message.text.startswith('/start'))
    )
)
user_router.callback_query.filter(~F.from_user.id.in_(ADMIN_IDS))

class ApplicationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_about = State()
    waiting_for_plans = State()
    waiting_for_community = State()
    waiting_for_platform = State()
    waiting_for_java_nickname = State()
    waiting_for_bedrock_nickname = State()
    waiting_for_skin = State()
    waiting_for_projects = State()
    waiting_for_referral = State()

class TicketStates(StatesGroup):
    waiting_for_message = State()
    chatting = State()

# Новые состояния для поэтапной анкеты
class ApplicationFormStates(StatesGroup):
    waiting_for_start = State()  # Начальное состояние, показывается политика
    waiting_for_name = State()   # Имя или ник
    waiting_for_age = State()    # Возраст
    waiting_for_about = State()  # О себе
    waiting_for_plans = State()  # Планы на сервере
    waiting_for_community = State()  # Что важно в сообществе
    waiting_for_platform = State()   # Выбор платформы
    waiting_for_java_nickname = State()  # Ник Java
    waiting_for_bedrock_nickname = State()  # Ник Bedrock
    waiting_for_skin = State()  # Скин (до 2 файлов)
    waiting_for_projects = State()  # Проекты (до 5 файлов)
    waiting_for_referral = State()  # Откуда узнали о сервере
    review_application = State()  # Просмотр анкеты перед отправкой

@user_router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    try:
        await state.clear()
        await add_user(message.from_user.id, message.from_user.username or str(message.from_user.id))
        await message.answer(
            "👋 Добро пожаловать в HorniMineBot!\n"
            "Выберите действие в меню ниже:",
            reply_markup=await get_main_menu(message.from_user.id in ADMIN_IDS, message.from_user.id)
        )
    except Exception as e:
        logger.error(f"Ошибка в start_command для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова позже.")

@user_router.callback_query(F.data == "create_application")
async def create_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application = await get_application_by_user_id(callback.from_user.id)
        if application and application[2] in ["pending", "approved", "rejected"]:
            await callback.message.answer(
                f"📝 У вас уже есть заявка (статус: {translate_status(application[2])})!",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
        else:
            # Начинаем процесс поэтапной анкеты
            await state.set_state(ApplicationFormStates.waiting_for_start)
            
            # Загружаем политику конфиденциальности из файла questions.md
            try:
                with open('questions.md', 'r', encoding='utf-8') as file:
                    policy_text = "\n".join(file.read().split('---')[0].strip().split('\n'))
            except Exception as e:
                logger.error(f"Ошибка при чтении файла с вопросами: {e}")
                policy_text = "Перед началом заполнения заявки, пожалуйста, ознакомьтесь с политикой конфиденциальности и правилами сервера."

            message = await callback.message.answer(
                policy_text,
                reply_markup=get_accept_policy_keyboard()
            )
            await state.update_data(last_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Ошибка в create_application для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка. Попробуйте снова.")
    await callback.answer()

@user_router.callback_query(F.data == "accept_policy", StateFilter(ApplicationFormStates.waiting_for_start))
async def process_policy_acceptance(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, callback.from_user.id, [last_message_id])
        await callback.message.delete()
        
        # Добавляем нового пользователя в базу и создаем заявку
        await add_user(callback.from_user.id, callback.from_user.username or str(callback.from_user.id))
        
        # Переходим к следующему шагу - имя или ник
        await state.set_state(ApplicationFormStates.waiting_for_name)
        
        # Загружаем вопрос из файла questions.md
        question = "Как к вам обращаться? (Имя или ник)"
        try:
            with open('questions.md', 'r', encoding='utf-8') as file:
                content = file.read().split('---')[1].strip()
                for line in content.split('\n'):
                    if "Как к вам обращаться?" in line:
                        question = line.strip()
                        break
        except Exception as e:
            logger.error(f"Ошибка при чтении вопроса: {e}")
        
        message = await callback.message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=message.message_id)
    except Exception as e:
        logger.error(f"Ошибка в process_policy_acceptance для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
    await callback.answer()

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_name), F.text)
async def process_name(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем имя
        player_name = message.text.strip()
        
        # Проверяем, есть ли у пользователя активная заявка
        application = await get_application_by_user_id(message.from_user.id)
        if not application:
            # Создаем новую заявку
            await add_application(message.from_user.id)
            application = await get_application_by_user_id(message.from_user.id)
            
        # Сохраняем имя в базе данных
        if application:
            await update_application_field(application[0], "player_name", player_name)
        
        # Переходим к следующему шагу - возраст
        await state.set_state(ApplicationFormStates.waiting_for_age)
        
        # Загружаем вопрос из файла questions.md
        question = "Сколько вам лет?"
        try:
            with open('questions.md', 'r', encoding='utf-8') as file:
                content = file.read().split('---')[1].strip()
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "Сколько вам лет?" in line:
                        question = line.strip()
                        break
        except Exception as e:
            logger.error(f"Ошибка при чтении вопроса: {e}")
        
        message = await message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=message.message_id, application_id=application[0])
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
    except Exception as e:
        logger.error(f"Ошибка в process_name для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_age), F.text)
async def process_age(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем возраст
        player_age = message.text.strip()
        application_id = data.get('application_id')
        
        # Сохраняем возраст в базе данных
        await update_application_field(application_id, "player_age", player_age)
        
        # Переходим к следующему шагу - о себе
        await state.set_state(ApplicationFormStates.waiting_for_about)
        
        # Загружаем вопрос из файла questions.md
        question = "Расскажите немного о себе: (Опыт игры, любимые аспекты Minecraft, участие в жизни сервера, идеи и проекты)"
        try:
            with open('questions.md', 'r', encoding='utf-8') as file:
                content = file.read().split('---')[1].strip()
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "Расскажите немного о себе:" in line:
                        question = line.strip()
                        if i+1 < len(lines) and lines[i+1].strip():
                            question += " " + lines[i+1].strip()
                        break
        except Exception as e:
            logger.error(f"Ошибка при чтении вопроса: {e}")
        
        message = await message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=message.message_id)
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
    except Exception as e:
        logger.error(f"Ошибка в process_age для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.callback_query(F.data == "back_to_previous_step")
async def back_to_previous_step(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        current_state = await state.get_state()
        await callback.message.delete()
        
        # Словарь переходов между состояниями
        state_transitions = {
            ApplicationFormStates.waiting_for_name: ApplicationFormStates.waiting_for_start,
            ApplicationFormStates.waiting_for_age: ApplicationFormStates.waiting_for_name,
            ApplicationFormStates.waiting_for_about: ApplicationFormStates.waiting_for_age,
            ApplicationFormStates.waiting_for_plans: ApplicationFormStates.waiting_for_about,
            ApplicationFormStates.waiting_for_community: ApplicationFormStates.waiting_for_plans,
            ApplicationFormStates.waiting_for_platform: ApplicationFormStates.waiting_for_community,
            ApplicationFormStates.waiting_for_java_nickname: ApplicationFormStates.waiting_for_platform,
            ApplicationFormStates.waiting_for_bedrock_nickname: ApplicationFormStates.waiting_for_platform,
            ApplicationFormStates.waiting_for_skin: ApplicationFormStates.waiting_for_java_nickname,  # В зависимости от предыдущего шага надо корректировать
            ApplicationFormStates.waiting_for_projects: ApplicationFormStates.waiting_for_skin,
            ApplicationFormStates.waiting_for_referral: ApplicationFormStates.waiting_for_projects,
            ApplicationFormStates.review_application: ApplicationFormStates.waiting_for_referral,
            None: None  # Для случаев, когда состояние неизвестно
        }
        
        # Определяем предыдущее состояние
        data = await state.get_data()
        previous_state = state_transitions.get(current_state)
        
        # Обработка специальных случаев
        if current_state == ApplicationFormStates.waiting_for_skin:
            platform = data.get('platform')
            previous_state = ApplicationFormStates.waiting_for_java_nickname if platform in ['java', 'both'] else ApplicationFormStates.waiting_for_platform
        
        if previous_state is None:
            # Возвращаемся в главное меню
            await state.clear()
            await callback.message.answer(
                "Заполнение анкеты отменено.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
            return
        
        # Удаляем сообщения и переходим к предыдущему шагу
        await state.set_state(previous_state)
        
        # Обрабатываем каждое состояние отдельно
        if previous_state == ApplicationFormStates.waiting_for_start:
            # Возвращаемся к показу политики
            try:
                with open('questions.md', 'r', encoding='utf-8') as file:
                    policy_text = "\n".join(file.read().split('---')[0].strip().split('\n'))
            except Exception as e:
                logger.error(f"Ошибка при чтении файла с вопросами: {e}")
                policy_text = "Перед началом заполнения заявки, пожалуйста, ознакомьтесь с политикой конфиденциальности и правилами сервера."
                
            message = await callback.message.answer(
                policy_text,
                reply_markup=get_accept_policy_keyboard()
            )
            await state.update_data(last_message_id=message.message_id)
            
        elif previous_state == ApplicationFormStates.waiting_for_name:
            # Возвращаемся к вопросу об имени
            question = "Как к вам обращаться? (Имя или ник)"
            try:
                with open('questions.md', 'r', encoding='utf-8') as file:
                    content = file.read().split('---')[1].strip()
                    for line in content.split('\n'):
                        if "Как к вам обращаться?" in line:
                            question = line.strip()
                            break
            except Exception as e:
                logger.error(f"Ошибка при чтении вопроса: {e}")
            
            message = await callback.message.answer(
                question,
                reply_markup=get_back_button_keyboard()
            )
            await state.update_data(last_message_id=message.message_id)
            
        # Обработка других состояний будет добавлена позже
        else:
            await callback.message.answer(
                "Переход к предыдущему шагу недоступен.",
                reply_markup=get_back_button_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в back_to_previous_step для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
    await callback.answer()

@user_router.callback_query(F.data == "edit_application")
async def edit_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
        data = await state.get_data()
        await delete_messages(bot, callback.from_user.id, [data.get("message_id")] + data.get("media_message_ids", []))
        await start_edit_application(callback, state, bot)
    except Exception as e:
        logger.error(f"Ошибка в edit_application для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при редактировании заявки.")
    await callback.answer()

@user_router.callback_query(F.data == "keep_description")
async def keep_description(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
        data = await state.get_data()
        await delete_messages(bot, callback.from_user.id, [data.get("message_id")] + data.get("media_message_ids", []))
        application = await get_application_by_user_id(callback.from_user.id)
        if not application:
            await callback.message.answer(
                "❌ Заявка не найдена.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
            await state.clear()
            return
        await state.set_state(ApplicationStates.waiting_for_media)
        message = await callback.message.answer(
            "📎 Отправьте новое фото, видео или документы (или выберите действие):",
            reply_markup=await get_application_media_keyboard(is_edit=True)
        )
        await state.update_data(message_id=message.message_id, media_message_ids=[])
    except Exception as e:
        logger.error(f"Ошибка в keep_description для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при редактировании заявки.")
    await callback.answer()

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_about), F.text)
async def process_about(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем текст 'О себе'
        about_text = message.text.strip()
        application_id = data.get('application_id')
        
        # Сохраняем в базе данных
        if application_id:
            await update_application_field(application_id, "player_about", about_text)
        
        # Переходим к следующему шагу - планы на сервере (вопрос 4)
        await state.set_state(ApplicationFormStates.waiting_for_plans)
        
        # Загружаем вопрос из файла questions.md
        question = "🎮 Как вы планируете проводить время на HorniMine?\n(Игровой стиль, предпочтения: строительство, приключения, торговля и т.д.)"
        
        new_message = await message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=new_message.message_id)
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
        
    except Exception as e:
        logger.error(f"Ошибка в process_about для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.message(StateFilter(ApplicationStates.waiting_for_skin), F.photo | F.document)
async def process_skin(message: Message, state: FSMContext, bot: Bot):
    try:
        data = await state.get_data()
        media = data.get("skin_media", [])
        
        if len(media) >= 2:
            await message.answer("🚫 Можно прикрепить не более 2 файлов скинов.")
            return
        
        if message.photo:
            file_id = message.photo[-1].file_id
            media_type = "photo"
        else:
            file_id = message.document.file_id
            media_type = "document"
        
        media.append({"file_id": file_id, "media_type": media_type})
        await state.update_data(skin_media=media)
        
        await message.answer(
            f"✅ Скин добавлен ({len(media)}/2). Прикрепите ещё или нажмите 'Продолжить'.",
            reply_markup=get_media_continue_keyboard("skin", len(media), 2)
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке скина: {e}")
        await message.answer("❌ Произошла ошибка при загрузке скина")

@user_router.callback_query(F.data == "send_application")
async def send_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        
        # Сохраняем заявку в БД
        application_id = await add_application_with_platform(
            callback.from_user.id,
            data.get("platform", "unknown")
        )
        
        # Обновляем все поля анкеты
        fields_mapping = [
            ("name", "player_name"),
            ("age", "player_age"),
            ("about", "player_about"),
            ("plans", "player_plans"),
            ("community", "player_community"),
            ("java_nickname", "player_nickname_java"),
            ("bedrock_nickname", "player_nickname_bedrock"),
            ("referral", "player_referral")
        ]
        
        for state_field, db_field in fields_mapping:
            if state_field in data:
                await update_application_field(
                    application_id, 
                    db_field, 
                    data[state_field]
                )
        
        # Сохраняем медиафайлы
        for media_type in ["skin", "projects"]:
            media_key = f"{media_type}_media"
            if media_key in data and data[media_key]:
                for media in data[media_key]:
                    await add_application_media(
                        application_id,
                        media["file_id"],
                        media["media_type"],
                        media_type
                    )
        
        # Сохраняем никнеймы в файл
        await save_players_to_file(application_id)
        
        # Отправляем уведомление админам
        admin_message = "🆕 Новая заявка на вайтлист!"
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔍 Подробности",
                callback_data=f"view_application_{application_id}"
            )]
        ])
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    admin_message,
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        # Отправляем подтверждение пользователю
        await callback.message.answer(
            "✅ Ваша заявка успешно отправлена на рассмотрение!\n"
            "Ожидайте ответа в течение 24 часов.",
            reply_markup=get_back_button()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отправке заявки: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при отправке заявки. Пожалуйста, попробуйте позже.",
            reply_markup=get_back_button()
        )
    finally:
        await state.clear()
        await callback.answer()

@user_router.callback_query(F.data == "view_application")
async def view_my_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        application = await get_application_by_user_id(callback.from_user.id)
        if not application:
            await callback.message.answer(
                "📭 У вас нет активных заявок.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
        else:
            media = await get_application_media(application[0])
            media_count = len(media)
            message = await callback.message.answer(
                f"📝 Ваша заявка #{application[0]}:\n"
                f"Статус: {translate_status(application[2])}\n"
                f"📄 Описание: {application[3] or 'Отсутствует'}\n"
                f"💬 Комментарий: {application[4] or 'Отсутствует'}\n"
                f"📎 Файлов: {media_count}\n"
                f"📅 Создано: {format_datetime(application[5])}\n"
                f"✏️ Редактирований: {application[6] or 0}/3",
                reply_markup=await get_application_menu(application[2], application[6] or 0)
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
                    logger.error(f"Ошибка отправки медиа {item[2]} пользователю {callback.from_user.id}: {e}")
                    await callback.message.answer("❌ Не удалось отправить одно из медиа.")
            await state.update_data(message_id=message.message_id, media_message_ids=media_message_ids)
    except Exception as e:
        logger.error(f"Ошибка в view_my_application для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре заявки.")
    await callback.answer()

@user_router.callback_query(F.data.in_(["back_to_main", "cancel"]))
async def back_to_main(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        data = await state.get_data()
        message_id = data.get("message_id")
        media_message_ids = data.get("media_message_ids", [])
        await delete_messages(bot, callback.from_user.id, [message_id] + media_message_ids)
        if await state.get_state() == ApplicationStates.waiting_for_about:
            application = await get_application_by_user_id(callback.from_user.id)
            if application and application[6] == 0:
                async with aiosqlite.connect('data/bot.db') as db:
                    await db.execute('DELETE FROM applications WHERE application_id = ?', (application[0],))
                    await db.commit()
                logger.info(f"Заявка #{application[0]} удалена при отмене")
        await callback.message.answer(
            "↩️ Вернулись в главное меню!",
            reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка в back_to_main для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при возврате в меню.")
    await callback.answer()

@user_router.callback_query(F.data == "create_ticket")
async def create_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        await callback.message.answer(
            "🆘 Вы можете написать нам на почту admin@hornimine.fun или задать вопрос здесь:",
            reply_markup=get_support_menu()
        )
        await state.update_data(message_id=callback.message.message_id, media_message_ids=[])
    except Exception as e:
        logger.error(f"Ошибка в create_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при открытии поддержки.")
    await callback.answer()

async def start_new_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        ticket_id = await add_ticket(callback.from_user.id)
        await state.set_state(TicketStates.waiting_for_message)
        message = await callback.message.answer(
            "🆘 Задайте вопрос (можно прикреплять фото, видео, документ, стикер), поддержка свяжется с вами в ближайшее время:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Отмена", callback_data="cancel")]
            ])
        )
        await state.update_data(ticket_id=ticket_id, message_id=message.message_id, media_message_ids=[], last_message_time=0)
    except Exception as e:
        logger.error(f"Ошибка в start_new_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании вопроса.")

@user_router.callback_query(F.data == "new_ticket")
async def new_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
        tickets = await get_open_tickets_by_user(callback.from_user.id)
        if tickets:
            message = await callback.message.answer(
                "🆘 У вас есть открытый вопрос. Продолжите общение или создайте новый:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💬 Продолжить чат", callback_data=f"view_my_ticket_{tickets[0][0]}")],
                    [InlineKeyboardButton(text="🆕 Новый вопрос", callback_data="force_new_ticket")],
                    [InlineKeyboardButton(text="↩️ Назад", callback_data="create_ticket")]
                ])
            )
            await state.update_data(message_id=message.message_id, media_message_ids=[])
        else:
            await start_new_ticket(callback, state, bot)
    except Exception as e:
        logger.error(f"Ошибка в new_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании нового вопроса.")
    await callback.answer()

@user_router.callback_query(F.data == "force_new_ticket")
async def force_new_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
        await start_new_ticket(callback, state, bot)
    except Exception as e:
        logger.error(f"Ошибка в force_new_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании нового вопроса.")
    await callback.answer()

@user_router.message(StateFilter(TicketStates.waiting_for_message))
async def process_ticket_message(message: Message, state: FSMContext, bot: Bot):
    try:
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        message_id = data.get("message_id")
        media_message_ids = data.get("media_message_ids", [])
        if not ticket_id:
            await message.answer("❌ Вопрос не найден. Попробуйте создать новый.")
            await state.clear()
            return
        content = message.text or message.caption or ""
        if message.text:
            message_type = "text"
        elif message.photo:
            content = message.photo[-1].file_id
            message_type = "photo"
            media_message_ids.append(message.message_id)
        elif message.video:
            content = message.video.file_id
            message_type = "video"
            media_message_ids.append(message.message_id)
        elif message.document:
            content = message.document.file_id
            message_type = "document"
            media_message_ids.append(message.message_id)
        elif message.sticker:
            content = message.sticker.file_id
            message_type = "sticker"
            media_message_ids.append(message.message_id)
        else:
            await message.answer("❌ Неподдерживаемый тип сообщения. Отправьте текст, фото, видео, документ или стикер.")
            return
        await add_ticket_message(ticket_id, message.from_user.id, message.message_id, message_type, content, "user")
        await delete_messages(bot, message.from_user.id, [message_id])
        message = await message.answer(
            "📬 Вопрос успешно отправлен! Если требуется, дополняйте свой вопрос. Чтобы завершить вопрос или выйти из чата, нажмите соответствующие кнопки ниже:",
            reply_markup=get_user_ticket_keyboard()
        )
        await state.update_data(message_id=message.message_id, media_message_ids=media_message_ids, last_message_time=message.date.timestamp())
        await state.set_state(TicketStates.chatting)
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await message.answer("❌ Вопрос не найден.")
            await state.clear()
            return
        user = await get_user(message.from_user.id)
        username = f"@{user[1]}" if user and user[1] else f"ID {message.from_user.id}"
        for admin_id in ADMIN_IDS:
            try:
                if message_type == "text":
                    await bot.send_message(
                        admin_id,
                        f"🆘 Новый вопрос #{ticket_id} от {username}:\n{content}",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ])
                    )
                elif message_type == "sticker":
                    await bot.send_sticker(
                        admin_id,
                        content,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ])
                    )
                else:
                    caption = f"🆘 Новый вопрос #{ticket_id} от {username}"
                    if message.caption:
                        caption += f"\n{message.caption}"
                    if message_type == "photo":
                        await bot.send_photo(admin_id, content, caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ]))
                    elif message_type == "video":
                        await bot.send_video(admin_id, content, caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ]))
                    elif message_type == "document":
                        await bot.send_document(admin_id, content, caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ]))
                logger.info(f"Уведомление о вопросе #{ticket_id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        if ticket[3]:
            try:
                if message_type == "text":
                    await bot.send_message(
                        ticket[3],
                        f"💬 Новое сообщение в вопросе #{ticket_id} от {username}:\n{content}"
                    )
                elif message_type == "sticker":
                    await bot.send_sticker(
                        ticket[3],
                        content,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💬 Перейти в чат", callback_data=f"chat_ticket_{ticket_id}")]
                        ])
                    )
                else:
                    caption = f"💬 Новое сообщение в вопросе #{ticket_id} от {username}"
                    if message.caption:
                        caption += f"\n{message.caption}"
                    if message_type == "photo":
                        await bot.send_photo(ticket[3], content, caption=caption)
                    elif message_type == "video":
                        await bot.send_video(ticket[3], content, caption=caption)
                    elif message_type == "document":
                        await bot.send_document(ticket[3], content, caption=caption)
                logger.info(f"Уведомление о сообщении в вопросе #{ticket_id} отправлено админу {ticket[3]}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {ticket[3]}: {e}")
    except Exception as e:
        logger.error(f"Ошибка в process_ticket_message для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при отправке сообщения.")

@user_router.message(StateFilter(TicketStates.chatting))
async def process_chat_message(message: Message, state: FSMContext, bot: Bot):
    """Обработчик сообщений пользователя в чате"""
    try:
        # Проверяем, что пользователь действительно в чате
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await message.answer(
                "❌ Необходимо создать вопрос для общения с поддержкой!",
                reply_markup=get_support_menu()
            )
            await state.clear()
            return
        
        # Получаем информацию о вопросе
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await message.answer(
                "❌ Вопрос не найден. Пожалуйста, создайте новый.",
                reply_markup=get_support_menu()
            )
            await state.clear()
            return
        
        # Проверяем, активен ли вопрос
        is_active = ticket[5] if len(ticket) > 5 else 0
        if is_active == 0:
            await message.answer(
                "❌ Этот вопрос уже закрыт. Пожалуйста, создайте новый вопрос.",
                reply_markup=get_support_menu()
            )
            await state.clear()
            return
        
        # Получаем содержимое и тип сообщения
        content, message_type = get_message_content_and_type(message)
        
        # Проверяем, поддерживается ли тип сообщения
        if message_type == "unknown":
            await message.answer(
                "❌ Неподдерживаемый тип сообщения. Отправьте текст, фото, видео, документ или стикер.",
                reply_markup=get_user_ticket_keyboard()
            )
            return
        
        # Сохраняем сообщение в базе данных
        await add_ticket_message(ticket_id, message.from_user.id, message.message_id, message_type, content, "user")
        
        # Отправляем подтверждение пользователю
        confirm_message = await message.answer(
            "✅ Сообщение отправлено администратору!",
            reply_markup=get_user_ticket_keyboard()
        )
        
        # Если у вопроса назначен администратор, отправляем ему сообщение
        admin_id = ticket[3]
        if admin_id:
            try:
                # Формируем имя пользователя для админа
                user = await get_user(message.from_user.id)
                username = f"@{user[1]}" if user and user[1] else f"ID {message.from_user.id}"
                
                # Отправляем сообщение администратору
                if message_type == "text":
                    await bot.send_message(
                        admin_id,
                        f"💬 Сообщение от {username} (вопрос #{ticket_id}):\n{content}"
                    )
                elif message_type == "sticker":
                    await bot.send_sticker(admin_id, content)
                    # Доп.сообщение для контекста
                    await bot.send_message(
                        admin_id,
                        f"👤 {username} отправил стикер в вопросе #{ticket_id}"
                    )
                else:
                    # Для медиа-файлов
                    caption = f"💬 Сообщение от {username} (вопрос #{ticket_id})"
                    if message.caption:
                        caption += f"\n{message.caption}"
                    
                    if message_type == "photo":
                        await bot.send_photo(admin_id, content, caption=caption)
                    elif message_type == "video":
                        await bot.send_video(admin_id, content, caption=caption)
                    elif message_type == "document":
                        await bot.send_document(admin_id, content, caption=caption)
                
                logger.info(f"Сообщение от пользователя {message.from_user.id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки сообщения админу {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Ошибка в process_chat_message для пользователя {message.from_user.id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при отправке сообщения.",
            reply_markup=await get_main_menu(message.from_user.id in ADMIN_IDS, message.from_user.id)
        )

@user_router.callback_query(F.data == "exit_chat")
async def exit_chat(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выход из чата по вопросу"""
    try:
        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")
        
        # Получаем данные из состояния
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        message_ids = data.get("message_ids", [])
        
        # Удаляем все сообщения чата
        if message_ids:
            await delete_messages(bot, callback.from_user.id, message_ids)
        
        # Очищаем состояние
        await state.clear()
        
        # Отправляем информацию о выходе из чата
        await callback.message.answer(
            f"↩️ Вы вышли из чата вопроса #{ticket_id}. Вы можете вернуться к нему позже.",
            reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
        )
        
        logger.info(f"Пользователь {callback.from_user.id} вышел из чата тикета {ticket_id}")
    
    except Exception as e:
        logger.error(f"Ошибка в exit_chat для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer(
            "❌ Произошла ошибка при выходе из чата.",
            reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
        )
    
    await callback.answer()

@user_router.callback_query(F.data == "close_user_ticket")
async def close_user_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Закрытие вопроса пользователем"""
    if callback.from_user.id in ADMIN_IDS:
        # Для админов эта функция обрабатывается в admin_router
        return
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await callback.message.answer("❌ Вопрос не найден.")
            await state.clear()
            return
        
        # Получаем информацию о тикете перед закрытием
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket:
            await callback.message.answer("❌ Вопрос не найден.")
            await state.clear()
            return
            
        # Проверяем, открыт ли тикет
        is_active = ticket[5] if len(ticket) > 5 else 0
        if is_active == 0:
            await callback.message.answer(
                "❌ Вопрос уже закрыт.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
            await state.clear()
            return
        
        message_id = data.get("message_id")
        media_message_ids = data.get("media_message_ids", [])
        if message_id or media_message_ids:
            await delete_messages(bot, callback.from_user.id, [message_id] + media_message_ids if message_id else media_message_ids)
        
        # Закрываем тикет
        success = await close_ticket(ticket_id)
        if not success:
            await callback.message.answer(
                "❌ Не удалось закрыть вопрос. Попробуйте позже.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
            return
        
        # Очищаем состояние пользователя
        await state.clear()
        
        # Отправляем подтверждение пользователю
        await callback.message.answer(
            "✅ Вопрос закрыт!",
            reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
        )
        
        # Получаем информацию о пользователе
        user = await get_user(callback.from_user.id)
        username = f"@{user[1]}" if user and user[1] else f"ID {callback.from_user.id}"
        
        # Уведомляем админа, назначенного на тикет
        admin_id = ticket[3]
        if admin_id:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ Пользователь {username} закрыл вопрос #{ticket_id}",
                    reply_markup=get_admin_menu()
                )
                logger.info(f"Уведомление о закрытии вопроса #{ticket_id} отправлено админу {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        # Дополнительно уведомляем остальных админов, если они не назначены на тикет
        for admin_id in ADMIN_IDS:
            if admin_id != ticket[3]:  # Не отправляем повторно назначенному админу
                try:
                    await bot.send_message(
                        admin_id,
                        f"✅ Пользователь {username} закрыл вопрос #{ticket_id}",
                        reply_markup=get_admin_menu()
                    )
                    logger.info(f"Уведомление о закрытии вопроса #{ticket_id} отправлено админу {admin_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
        
        logger.info(f"Вопрос #{ticket_id} закрыт пользователем {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в close_user_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при закрытии вопроса.")
    await callback.answer()

@user_router.callback_query(F.data == "view_my_tickets")
async def view_my_tickets(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        tickets = await get_open_tickets_by_user(callback.from_user.id)
        if not tickets:
            await callback.message.answer(
                "📭 У вас нет открытых вопросов.",
                reply_markup=get_support_menu()
            )
        else:
            await callback.message.answer(
                "📬 Ваши открытые вопросы:",
                reply_markup=get_user_tickets_menu(tickets)
            )
        await state.update_data(media_message_ids=[])
    except Exception as e:
        logger.error(f"Ошибка в view_my_tickets для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре вопросов.")
    await callback.answer()

@user_router.callback_query(F.data.startswith("view_my_ticket_"))
async def view_my_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        ticket_id = int(callback.data.split("_")[3])
        ticket = await get_ticket_by_id(ticket_id)
        if not ticket or ticket[1] != callback.from_user.id:
            await callback.message.answer(
                "❌ Вопрос не найден или доступ запрещён.",
                reply_markup=await get_main_menu(callback.from_user.id in ADMIN_IDS, callback.from_user.id)
            )
            return
        await state.set_state(TicketStates.chatting)
        message = await callback.message.answer(
            "💬 Вы в чате с поддержкой. Отправляйте сообщения или используйте кнопки ниже:",
            reply_markup=get_user_ticket_keyboard()
        )
        await state.update_data(ticket_id=ticket_id, message_id=message.message_id, media_message_ids=[], last_message_time=0)
    except Exception as e:
        logger.error(f"Ошибка в view_my_ticket для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при просмотре вопроса.")
    await callback.answer()

@user_router.callback_query(F.data == "about_server")
async def about_server(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
    try:
        await callback.message.answer(
            "ℹ️ О сервере HorniMine:\n"
            "HorniMine — это крутой Minecraft-сервер для весёлой игры с друзьями!\n"
            "🌍 IP: play.hornimine.fun\n"
            "🎮 Версия: 1.20.1\n"
            "📢 Discord: discord.gg/hornimine\n"
            "✉️ Поддержка: admin@hornimine.fun",
            reply_markup=get_back_button()
        )
    except Exception as e:
        logger.error(f"Ошибка в about_server для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о сервере.")
    await callback.answer()

@user_router.callback_query()
async def unknown_callback_user(callback: CallbackQuery):
    """Обработчик неизвестных callback-запросов"""
    try:
        # Проверяем, является ли пользователь админом
        if callback.from_user.id in ADMIN_IDS:
            # Для админов не отвечаем, так как это может быть админский callback
            await callback.answer()
            return
            
        logger.warning(f"Необработанный пользовательский callback: {callback.data} от пользователя {callback.from_user.id}")
        await callback.answer(
            "🤔 Эта функция пока не доступна или у вас нет прав для её использования. Пожалуйста, вернитесь в главное меню.",
            show_alert=True
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке неизвестного callback: {e}")
        await callback.answer("Произошла ошибка. Попробуйте снова.")

@user_router.message(F.text.startswith("/start"))
async def handle_start_command(message: Message, state: FSMContext):
    """Обработка /start для пользователей"""
    await state.clear()
    await add_user(message.from_user.id, message.from_user.username or str(message.from_user.id))
    
    # Проверяем, есть ли у пользователя активный чат
    active_state = await state.get_state()
    if active_state == TicketStates.chatting.__str__():
        # Сбрасываем состояние чата
        await state.clear()
    
    await message.answer(
        "👋 Добро пожаловать в HorniMineBot!\n"
        "Выберите действие в меню ниже:",
        reply_markup=await get_main_menu(message.from_user.id in ADMIN_IDS, message.from_user.id)
    )
    logger.info(f"Пользователь {message.from_user.id} использовал команду /start")

@user_router.message()
async def unknown_message_user(message: Message, state: FSMContext):
    """Обработчик неизвестных сообщений для пользователей"""
    try:
        current_state = await state.get_state()
        
        # Если пользователь отправил команду /start, обрабатываем её
        if message.text and message.text.startswith('/start'):
            await handle_start_command(message, state)
            return
        
        logger.warning(f"Необработанное сообщение от пользователя {message.from_user.id}, состояние: {current_state}")
        
        # Если пользователь не в каком-то определенном состоянии, отвечаем
        if not current_state:
            await message.answer(
                "🤔 Я вас не понимаю. Пожалуйста, используйте меню или команду /start для начала работы.",
                reply_markup=await get_main_menu(message.from_user.id in ADMIN_IDS, message.from_user.id)
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке неизвестного сообщения: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте снова использовать /start.")

@user_router.message(F.text == "📝 Подать заявку")
async def start_application(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "1. Как к вам обращаться? (Имя или ник)",
        reply_markup=get_back_button_keyboard()
    )
    await state.set_state(ApplicationStates.waiting_for_name)

@user_router.message(ApplicationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "2. Сколько вам лет?",
        reply_markup=get_back_button_keyboard()
    )
    await state.set_state(ApplicationStates.waiting_for_age)

@user_router.message(ApplicationStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text)
    await message.answer(
        "3. Расскажите немного о себе: (Опыт игры, любимые аспекты Minecraft, участие в жизни сервера, идеи и проекты)",
        reply_markup=get_back_button_keyboard()
    )
    await state.set_state(ApplicationStates.waiting_for_about)

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_about), F.text)
async def process_about(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем текст 'О себе'
        about_text = message.text.strip()
        application_id = data.get('application_id')
        
        # Сохраняем в базе данных
        if application_id:
            await update_application_field(application_id, "player_about", about_text)
        
        # Переходим к следующему шагу - планы на сервере (вопрос 4)
        await state.set_state(ApplicationFormStates.waiting_for_plans)
        
        # Загружаем вопрос из файла questions.md
        question = "🎮 Как вы планируете проводить время на HorniMine?\n(Игровой стиль, предпочтения: строительство, приключения, торговля и т.д.)"
        
        new_message = await message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=new_message.message_id)
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
        
    except Exception as e:
        logger.error(f"Ошибка в process_about для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_plans), F.text)
async def process_plans(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем планы на сервере
        plans_text = message.text.strip()
        application_id = data.get('application_id')
        
        # Сохраняем в базе данных
        if application_id:
            await update_application_field(application_id, "player_plans", plans_text)
        
        # Переходим к следующему шагу - вопрос о сообществе (вопрос 5)
        await state.set_state(ApplicationFormStates.waiting_for_community)
        
        # Вопрос 5 из questions.md
        question = "💙 Что для вас важно в дружелюбном сообществе?\n(Честность, уважение, поддержка, свобода самовыражения и т.п.)"
        
        new_message = await message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=new_message.message_id)
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
        
    except Exception as e:
        logger.error(f"Ошибка в process_plans для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.message(StateFilter(ApplicationFormStates.waiting_for_community), F.text)
async def process_community(message: Message, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущие сообщения
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, message.from_user.id, [last_message_id])
        
        # Сохраняем ответ о сообществе
        community_text = message.text.strip()
        application_id = data.get('application_id')
        
        # Сохраняем в базе данных
        if application_id:
            await update_application_field(application_id, "player_community", community_text)
        
        # Переходим к выбору платформы (вопрос 6)
        await state.set_state(ApplicationFormStates.waiting_for_platform)
        
        # Вопрос 6 - выбор платформы с кнопками!
        question = "🎮 На какой платформе вы играете?"
        
        # Импортируем клавиатуру для выбора платформы
        from keyboards import get_platform_choice_keyboard
        
        new_message = await message.answer(
            question,
            reply_markup=get_platform_choice_keyboard()
        )
        await state.update_data(last_message_id=new_message.message_id)
        
        # Удаляем сообщение пользователя для чистоты чата
        await safe_message_delete(message)
        
    except Exception as e:
        logger.error(f"Ошибка в process_community для пользователя {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")

@user_router.callback_query(F.data.startswith("platform_"), StateFilter(ApplicationFormStates.waiting_for_platform))
async def process_platform_choice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        # Удаляем предыдущее сообщение
        data = await state.get_data()
        if last_message_id := data.get('last_message_id'):
            await delete_messages(bot, callback.from_user.id, [last_message_id])
        await callback.message.delete()
        
        # Получаем выбранную платформу из callback_data
        platform = callback.data.split("_")[1]  # platform_java -> java
        application_id = data.get('application_id')
        
        # Сохраняем платформу в базе данных
        if application_id:
            await update_application_field(application_id, "player_platform", platform)
        
        # Сохраняем платформу в состоянии для дальнейшего использования
        await state.update_data(platform=platform)
        
        # В зависимости от платформы переходим к разным вопросам
        if platform in ["java", "both"]:
            # Если выбрал Java или обе платформы - спрашиваем Java никнейм
            await state.set_state(ApplicationFormStates.waiting_for_java_nickname)
            question = "⚡ Введите свой никнейм Java\n(Без пробелов и лишних символов):"
        else:
            # Если выбрал только Bedrock - сразу спрашиваем Bedrock никнейм
            await state.set_state(ApplicationFormStates.waiting_for_bedrock_nickname)
            question = "🟢 Введите свой никнейм Bedrock\n(Без пробелов и лишних символов):"
        
        new_message = await callback.message.answer(
            question,
            reply_markup=get_back_button_keyboard()
        )
        await state.update_data(last_message_id=new_message.message_id)
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_platform_choice для пользователя {callback.from_user.id}: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        await callback.answer()

@user_router.message(ApplicationStates.waiting_for_java_nickname)
async def process_java_nickname(message: Message, state: FSMContext):
    await state.update_data(java_nickname=message.text)
    await message.answer(
        "9. Прикрепите фото или документ вашего скина:",
        reply_markup=get_back_button_keyboard()
    )
    await state.set_state(ApplicationStates.waiting_for_skin)

@user_router.message(ApplicationStates.waiting_for_bedrock_nickname)
async def process_bedrock_nickname(message: Message, state: FSMContext):
    await state.update_data(bedrock_nickname=message.text)
    await message.answer(
        "9. Прикрепите фото или документ вашего скина:",
        reply_markup=get_back_button_keyboard()
    )
    await state.set_state(ApplicationStates.waiting_for_skin)

@user_router.message(ApplicationStates.waiting_for_skin, F.photo | F.document)
async def process_skin(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    media = data.get("skin_media", [])
    
    if len(media) >= 2:
        await message.answer("Можно прикрепить не более 2 файлов скинов.")
        return
    
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    else:
        file_id = message.document.file_id
        media_type = "document"
    
    media.append({"file_id": file_id, "media_type": media_type})
    await state.update_data(skin_media=media)
    
    await message.answer(
        f"Скин добавлен ({len(media)}/2). Прикрепите ещё или нажмите 'Продолжить'.",
        reply_markup=get_media_continue_keyboard("skin", len(media), 2)
    )

@user_router.callback_query(F.data == "send_application")
async def send_application(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    
    # Сохраняем заявку в БД
    application_id = await add_application_with_platform(
        callback.from_user.id,
        data.get("platform")
    )
    
    # Обновляем все поля анкеты
    fields = [
        ("name", "player_name"),
        ("age", "player_age"),
        ("about", "player_about"),
        ("plans", "player_plans"),
        ("community", "player_community"),
        ("java_nickname", "player_nickname_java"),
        ("bedrock_nickname", "player_nickname_bedrock"),
        ("referral", "player_referral")
    ]
    
    for state_field, db_field in fields:
        if state_field in data:
            await update_application_field(application_id, db_field, data[state_field])
    
    # Сохраняем медиафайлы
    for media_type in ["skin", "projects"]:
        if f"{media_type}_media" in data:
            for media in data[f"{media_type}_media"]:
                await add_application_media(
                    application_id,
                    media["file_id"],
                    media["media_type"],
                    media_type
                )
    
    # Сохраняем никнеймы в файл
    await save_players_to_file(application_id)
    
    # Отправляем уведомление админам
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            "📬 Новая заявка на вайтлист!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Подробности",
                    callback_data=f"view_application_{application_id}"
                )]
            ])
        )
    
    await callback.message.answer(
        "✅ Ваша заявка отправлена на рассмотрение!",
        reply_markup=get_back_button()
    )
    await state.clear()
    await callback.answer()
