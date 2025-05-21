import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def init_db():
    logger.info("Initializing database...")
    async with aiosqlite.connect('data/bot.db') as db:
        # Таблица users
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TIMESTAMP
            )
        ''')
        async with db.execute('PRAGMA table_info(users)') as cursor:
            columns = [col[1] for col in await cursor.fetchall()]
            if 'created_at' not in columns:
                logger.info("Adding created_at column to users table")
                await db.execute('ALTER TABLE users ADD COLUMN created_at TIMESTAMP')
                await db.execute('UPDATE users SET created_at = ? WHERE created_at IS NULL', (datetime.now().isoformat(),))
                logger.info("Updated created_at for existing users")

        # Таблица applications
        await db.execute('''
            CREATE TABLE IF NOT EXISTS applications (
                application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'pending',
                description TEXT,
                comment TEXT,
                created_at TIMESTAMP,
                edit_count INTEGER DEFAULT 0,
                player_name TEXT,
                player_age TEXT,
                player_about TEXT,
                player_plans TEXT,
                player_community TEXT,
                player_platform TEXT,
                player_nickname_java TEXT,
                player_nickname_bedrock TEXT,
                player_referral TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        async with db.execute('PRAGMA table_info(applications)') as cursor:
            columns = [col[1] for col in await cursor.fetchall()]
            if 'edit_count' not in columns:
                logger.info("Adding edit_count column to applications table")
                await db.execute('ALTER TABLE applications ADD COLUMN edit_count INTEGER')
                await db.execute('UPDATE applications SET edit_count = 0 WHERE edit_count IS NULL')
                logger.info("Updated edit_count for existing applications")
            
            # Добавление новых столбцов для анкеты, если их ещё нет
            new_columns = [
                'player_name', 'player_age', 'player_about', 'player_plans',
                'player_community', 'player_platform', 'player_nickname_java',
                'player_nickname_bedrock', 'player_referral'
            ]
            
            for col in new_columns:
                if col not in columns:
                    logger.info(f"Adding {col} column to applications table")
                    await db.execute(f'ALTER TABLE applications ADD COLUMN {col} TEXT')
                    logger.info(f"Added {col} column to applications table")

        # Таблица application_media
        await db.execute('''
            CREATE TABLE IF NOT EXISTS application_media (
                media_id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                file_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                media_category TEXT DEFAULT 'general',
                FOREIGN KEY (application_id) REFERENCES applications (application_id)
            )
        ''')
        
        async with db.execute('PRAGMA table_info(application_media)') as cursor:
            columns = [col[1] for col in await cursor.fetchall()]
            if 'media_category' not in columns:
                logger.info("Adding media_category column to application_media table")
                await db.execute('ALTER TABLE application_media ADD COLUMN media_category TEXT DEFAULT "general"')

        # Таблица tickets
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'open',
                admin_id INTEGER,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Таблица ticket_messages
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ticket_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                telegram_message_id INTEGER,
                message_type TEXT,
                content TEXT,
                sender_type TEXT,
                username TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        async with db.execute('PRAGMA table_info(ticket_messages)') as cursor:
            columns = [col[1] for col in await cursor.fetchall()]
            if 'sender_type' not in columns:
                logger.info("Adding sender_type column to ticket_messages table")
                await db.execute('ALTER TABLE ticket_messages ADD COLUMN sender_type TEXT')
                await db.execute('UPDATE ticket_messages SET sender_type = "user" WHERE sender_type IS NULL')
                logger.info("Updated sender_type for existing ticket_messages")

        await db.commit()
    logger.info("Database tables created successfully")

async def add_user(user_id: int, username: str):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
        ''', (user_id, username, datetime.now().isoformat()))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT user_id, username, created_at
            FROM users
            WHERE user_id = ?
        ''', (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_application(user_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            INSERT INTO applications (user_id, status, created_at, edit_count)
            VALUES (?, 'pending', ?, 0)
        ''', (user_id, datetime.now().isoformat()))
        await db.commit()

async def get_application_by_user_id(user_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT application_id, user_id, status, description, comment, created_at, edit_count
            FROM applications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_application_by_id(application_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT application_id, user_id, status, description, comment, created_at, edit_count
            FROM applications
            WHERE application_id = ?
        ''', (application_id,)) as cursor:
            return await cursor.fetchone()

async def update_application(application_id: int, description: str, edit_count: int, status: str):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            UPDATE applications
            SET description = ?, edit_count = ?, status = ?
            WHERE application_id = ?
        ''', (description, edit_count, status, application_id))
        await db.commit()

async def update_application_status(application_id: int, status: str, comment: str):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            UPDATE applications
            SET status = ?, comment = ?
            WHERE application_id = ?
        ''', (status, comment, application_id))
        await db.commit()

async def update_application_comment(application_id: int, comment: str):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            UPDATE applications
            SET comment = ?
            WHERE application_id = ?
        ''', (comment, application_id))
        await db.commit()

async def add_application_media(application_id: int, file_id: str, media_type: str):
    async with aiosqlite.connect('data/bot.db') as db:
        await db.execute('''
            INSERT INTO application_media (application_id, file_id, media_type)
            VALUES (?, ?, ?)
        ''', (application_id, file_id, media_type))
        await db.commit()
        logger.info(f"Медиа добавлено для заявки #{application_id}: {media_type}")

async def delete_application_media(application_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                DELETE FROM application_media
                WHERE application_id = ?
            ''', (application_id,))
            await db.commit()
        logger.info(f"Все медиа для заявки #{application_id} удалены")
    except Exception as e:
        logger.error(f"Ошибка удаления медиа для заявки #{application_id}: {e}")

async def get_application_media(application_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT media_id, application_id, file_id, media_type
            FROM application_media
            WHERE application_id = ?
        ''', (application_id,)) as cursor:
            return await cursor.fetchall()

async def get_pending_applications():
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('''
            SELECT application_id, user_id, status, description, comment, created_at, edit_count
            FROM applications
            WHERE status = 'pending'
            ORDER BY created_at
        ''') as cursor:
            return await cursor.fetchall()

async def delete_application(application_id: int):
    async with aiosqlite.connect('data/bot.db') as db:
        async with db.execute('SELECT user_id FROM applications WHERE application_id = ?', (application_id,)) as cursor:
            user_id = await cursor.fetchone()
        await db.execute('''
            DELETE FROM application_media
            WHERE application_id = ?
        ''', (application_id,))
        await db.execute('''
            DELETE FROM applications
            WHERE application_id = ?
        ''', (application_id,))
        await db.commit()
        return user_id[0] if user_id else None

async def add_ticket(user_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                INSERT INTO tickets (user_id, status, created_at)
                VALUES (?, 'open', ?)
            ''', (user_id, datetime.now().isoformat()))
            await db.commit()
                
            async with db.execute('''
                SELECT ticket_id
                FROM tickets
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,)) as cursor:
                ticket = await cursor.fetchone()
                if ticket:
                    logger.info(f"Создан новый тикет #{ticket[0]} от пользователя {user_id}")
                    return ticket[0]
                else:
                    logger.error(f"Ошибка создания тикета: не удалось получить ticket_id")
                    return None
    except Exception as e:
        logger.error(f"Ошибка при создании тикета для пользователя {user_id}: {e}")
        return None

async def get_ticket_by_id(ticket_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT ticket_id, user_id, status, admin_id, created_at, 
                       CASE WHEN status = 'open' THEN 1 ELSE 0 END as is_active
                FROM tickets
                WHERE ticket_id = ?
            ''', (ticket_id,)) as cursor:
                ticket = await cursor.fetchone()
                if not ticket:
                    logger.warning(f"Тикет #{ticket_id} не найден")
                return ticket
    except Exception as e:
        logger.error(f"Ошибка при получении тикета #{ticket_id}: {e}")
        return None

async def assign_admin_to_ticket(ticket_id: int, admin_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                UPDATE tickets
                SET admin_id = ?
                WHERE ticket_id = ?
            ''', (admin_id, ticket_id))
            await db.commit()
            logger.info(f"Админ {admin_id} назначен на тикет #{ticket_id}")
    except Exception as e:
        logger.error(f"Ошибка при назначении админа {admin_id} на тикет #{ticket_id}: {e}")

async def add_ticket_message(ticket_id: int, user_id: int, telegram_message_id: int, message_type: str, content: str, sender_type: str):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            # Проверяем, что тикет существует и открыт
            async with db.execute('SELECT status FROM tickets WHERE ticket_id = ?', (ticket_id,)) as cursor:
                ticket = await cursor.fetchone()
                if not ticket:
                    logger.warning(f"Попытка добавить сообщение в несуществующий тикет #{ticket_id}")
                    return False
                if ticket[0] != 'open':
                    logger.warning(f"Попытка добавить сообщение в закрытый тикет #{ticket_id}")
                    return False
            
            user = await get_user(user_id)
            username = user[1] if user else str(user_id)
            
            await db.execute('''
                INSERT INTO ticket_messages (
                    ticket_id, user_id, telegram_message_id, 
                    message_type, content, sender_type, 
                    username, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, user_id, telegram_message_id, 
                message_type, content, sender_type, 
                username, datetime.now().isoformat()
            ))
            await db.commit()
            logger.info(f"Добавлено сообщение в тикет #{ticket_id} от {sender_type} {username}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении сообщения в тикет #{ticket_id}: {e}")
        return False

async def get_ticket_messages(ticket_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT 
                    message_id, ticket_id, user_id, 
                    message_type, content, created_at, 
                    sender_type, username
            FROM ticket_messages
            WHERE ticket_id = ?
            ORDER BY created_at
        ''', (ticket_id,)) as cursor:
                messages = await cursor.fetchall()
                if not messages:
                    logger.info(f"В тикете #{ticket_id} нет сообщений")
                return messages
    except Exception as e:
        logger.error(f"Ошибка при получении сообщений тикета #{ticket_id}: {e}")
        return []

async def close_ticket(ticket_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            # Проверяем, что тикет существует и открыт
            async with db.execute('SELECT status FROM tickets WHERE ticket_id = ?', (ticket_id,)) as cursor:
                ticket = await cursor.fetchone()
                if not ticket:
                    logger.warning(f"Попытка закрыть несуществующий тикет #{ticket_id}")
                    return False
                if ticket[0] != 'open':
                    logger.warning(f"Попытка закрыть уже закрытый тикет #{ticket_id}")
                    return False
            
            await db.execute('''
                UPDATE tickets
                SET status = 'closed'
                WHERE ticket_id = ?
            ''', (ticket_id,))
            await db.commit()
            logger.info(f"Тикет #{ticket_id} закрыт")
            return True
    except Exception as e:
        logger.error(f"Ошибка при закрытии тикета #{ticket_id}: {e}")
        return False

async def get_open_tickets():
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT ticket_id, user_id, status, admin_id, created_at,
                       CASE WHEN status = 'open' THEN 1 ELSE 0 END as is_active
            FROM tickets
            WHERE status = 'open'
            ORDER BY created_at
        ''') as cursor:
                tickets = await cursor.fetchall()
                logger.info(f"Получено {len(tickets)} открытых тикетов")
                return tickets
    except Exception as e:
        logger.error(f"Ошибка при получении открытых тикетов: {e}")
        return []

async def get_open_tickets_by_user(user_id: int):
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT ticket_id, user_id, status, admin_id, created_at,
                       CASE WHEN status = 'open' THEN 1 ELSE 0 END as is_active
            FROM tickets
            WHERE user_id = ? AND status = 'open'
                ORDER BY created_at DESC
        ''', (user_id,)) as cursor:
                tickets = await cursor.fetchall()
                logger.info(f"Получено {len(tickets)} открытых тикетов пользователя {user_id}")
                return tickets
    except Exception as e:
        logger.error(f"Ошибка при получении открытых тикетов пользователя {user_id}: {e}")
        return []

async def update_application_field(application_id: int, field_name: str, value: str):
    """Обновляет конкретное поле заявки"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute(f'''
                UPDATE applications
                SET {field_name} = ?
                WHERE application_id = ?
            ''', (value, application_id))
            await db.commit()
            logger.info(f"Обновлено поле {field_name} для заявки #{application_id}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении поля {field_name} для заявки #{application_id}: {e}")
        return False

async def add_application_with_platform(user_id: int, platform: str):
    """Создает новую заявку с указанной платформой"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                INSERT INTO applications (user_id, status, created_at, edit_count, player_platform)
                VALUES (?, 'pending', ?, 0, ?)
            ''', (user_id, datetime.now().isoformat(), platform))
            await db.commit()
            
            async with db.execute('''
                SELECT application_id
                FROM applications
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,)) as cursor:
                application = await cursor.fetchone()
                if application:
                    logger.info(f"Создана новая заявка #{application[0]} от пользователя {user_id} с платформой {platform}")
                    return application[0]
                else:
                    logger.error(f"Ошибка создания заявки: не удалось получить application_id")
                    return None
    except Exception as e:
        logger.error(f"Ошибка при создании заявки для пользователя {user_id}: {e}")
        return None

async def save_players_to_file(application_id: int):
    """
    Сохраняет никнеймы игроков в файл data/players.txt в формате:
    username,platform,nickname_java,nickname_bedrock
    """
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT u.username, a.player_platform, a.player_nickname_java, a.player_nickname_bedrock
                FROM applications a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.application_id = ?
            ''', (application_id,)) as cursor:
                player_data = await cursor.fetchone()
                
                if player_data:
                    username, platform, nickname_java, nickname_bedrock = player_data
                    with open('data/players.txt', 'a', encoding='utf-8') as f:
                        f.write(f"{username},{platform},{nickname_java or ''},{nickname_bedrock or ''}\n")
                    logger.info(f"Никнеймы игрока {username} сохранены в файл")
    except Exception as e:
        logger.error(f"Ошибка при сохранении никнеймов в файл: {e}")

async def execute_whitelist_command(nickname: str, platform: str):
    """
    Выполняет команду whitelist/fwhitelist через screen
    
    :param nickname: Никнейм игрока
    :param platform: Платформа (java/bedrock)
    """
    import subprocess
    
    try:
        if platform == "java":
            command = f"screen -DD -RR server -X stuff 'whitelist add {nickname}\n'"
        elif platform == "bedrock":
            command = f"screen -DD -RR server -X stuff 'fwhitelist add {nickname}\n'"
        else:
            logger.error(f"Неизвестная платформа для whitelist: {platform}")
            return False
        
        # Выполняем команду
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Успешно выполнена команда whitelist для {nickname} ({platform})")
            return True
        else:
            logger.error(f"Ошибка выполнения команды whitelist: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды whitelist: {e}")
        return False

async def get_full_application_data(application_id: int):
    """Получает все данные заявки для отображения админам"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT 
                    a.application_id, a.user_id, a.status, a.description, a.comment, a.created_at, a.edit_count,
                    a.player_name, a.player_age, a.player_about, a.player_plans, a.player_community,
                    a.player_platform, a.player_nickname_java, a.player_nickname_bedrock, a.player_referral,
                    u.username
                FROM applications a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.application_id = ?
            ''', (application_id,)) as cursor:
                application = await cursor.fetchone()
                if not application:
                    logger.warning(f"Заявка #{application_id} не найдена")
                return application
    except Exception as e:
        logger.error(f"Ошибка при получении полных данных заявки #{application_id}: {e}")
        return None

async def add_skin_media(application_id: int, file_id: str, media_type: str):
    """Добавляет медиафайл скина игрока"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                INSERT INTO application_media (application_id, file_id, media_type, media_category)
                VALUES (?, ?, ?, 'skin')
            ''', (application_id, file_id, media_type))
            await db.commit()
            logger.info(f"Медиа скина добавлено для заявки #{application_id}: {media_type}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении медиа скина для заявки #{application_id}: {e}")
        return False

async def add_project_media(application_id: int, file_id: str, media_type: str):
    """Добавляет медиафайл проекта игрока"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            await db.execute('''
                INSERT INTO application_media (application_id, file_id, media_type, media_category)
                VALUES (?, ?, ?, 'project')
            ''', (application_id, file_id, media_type))
            await db.commit()
            logger.info(f"Медиа проекта добавлено для заявки #{application_id}: {media_type}")
            return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении медиа проекта для заявки #{application_id}: {e}")
        return False

async def get_application_media_by_category(application_id: int, category: str):
    """Получает медиафайлы заявки по определенной категории"""
    try:
        async with aiosqlite.connect('data/bot.db') as db:
            async with db.execute('''
                SELECT media_id, application_id, file_id, media_type
                FROM application_media
                WHERE application_id = ? AND media_category = ?
            ''', (application_id, category)) as cursor:
                return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении медиа категории {category} для заявки #{application_id}: {e}")
        return []

async def execute_whitelist_command(nickname: str, platform: str):
    """
    Выполняет команду whitelist/fwhitelist через screen
    
    :param nickname: Никнейм игрока
    :param platform: Платформа (java/bedrock)
    """
    import subprocess
    
    try:
        if platform == "java":
            command = f"screen -DD -RR server -X stuff 'whitelist add {nickname}\n'"
        elif platform == "bedrock":
            command = f"screen -DD -RR server -X stuff 'fwhitelist add {nickname}\n'"
        else:
            logger.error(f"Неизвестная платформа для whitelist: {platform}")
            return False
        
        # Выполняем команду
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Успешно выполнена команда whitelist для {nickname} ({platform})")
            return True
        else:
            logger.error(f"Ошибка выполнения команды whitelist: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды whitelist: {e}")
        return False
