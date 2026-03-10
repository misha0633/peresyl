import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio

# Настройки
BOT_TOKEN = '8724423809:AAEeLx9F4Xku8AAHqrRYCl-UWqrsc4TTRME'  # Ваш токен
SOURCE_GROUP_ID = -5272037357  # ID группы откуда пересылаем (замените на свой)
TARGET_CHANNEL_ID = -1003079468911  # ID канала куда пересылаем (замените на свой)
OWNER_USERNAME = 'piyuqw'  # Юзернейм владельца (без @)

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Словарь для хранения связи сообщений с автором
post_authors = {}

async def forward_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка всех сообщений из группы в канал с кнопками"""
    
    try:
        # Проверяем, что сообщение из нужной группы
        if str(update.effective_chat.id) != str(SOURCE_GROUP_ID):
            return

        author = update.effective_user
        message = update.effective_message

        # Пропускаем сообщения от самого бота
        if author and author.id == context.bot.id:
            return
        
        # Берем текст сообщения (без добавления информации об отправителе)
        message_text = message.text or message.caption or ""
        
        if not message_text and not message.media:
            # Если сообщение пустое - уведомляем в группу
            await context.bot.send_message(
                chat_id=SOURCE_GROUP_ID,
                text="❌ Сообщение пустое. Пересылка отменена."
            )
            return
        
        # Создаем кнопки
        keyboard = []
        
        # Кнопка для связи с автором
        if author and author.username:
            # Если есть username - делаем кнопку с переходом в ЛС
            keyboard.append([InlineKeyboardButton("📨 Откликнуться", url=f"https://t.me/{author.username}")])
        elif author:
            # Если нет username, но есть ID - делаем callback кнопку
            keyboard.append([InlineKeyboardButton("📨 Откликнуться (нет username)", callback_data=f"respond_no_username_{author.id}")])
        else:
            keyboard.append([InlineKeyboardButton("📨 Откликнуться", callback_data="respond_no_sender")])
        
        # Кнопка "Не могу написать" - отправляет инфо о нажавшем автору
        if author:
            keyboard.append([InlineKeyboardButton("❌ Не могу написать", callback_data=f"cannot_{author.id}")])
        else:
            keyboard.append([InlineKeyboardButton("❌ Не могу написать", callback_data="cannot_unknown")])
        
        # Кнопка для связи с владельцем
        if OWNER_USERNAME:
            keyboard.append([InlineKeyboardButton("👤 Владелец", url=f"https://t.me/{OWNER_USERNAME}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение в канал
        if message.text:
            sent_message = await context.bot.send_message(
                chat_id=TARGET_CHANNEL_ID,
                text=message_text,
                reply_markup=reply_markup
            )
        elif message.photo:
            sent_message = await context.bot.send_photo(
                chat_id=TARGET_CHANNEL_ID,
                photo=message.photo[-1].file_id,
                caption=message_text if message_text else None,
                reply_markup=reply_markup
            )
        elif message.document:
            sent_message = await context.bot.send_document(
                chat_id=TARGET_CHANNEL_ID,
                document=message.document.file_id,
                caption=message_text if message_text else None,
                reply_markup=reply_markup
            )
        elif message.video:
            sent_message = await context.bot.send_video(
                chat_id=TARGET_CHANNEL_ID,
                video=message.video.file_id,
                caption=message_text if message_text else None,
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=SOURCE_GROUP_ID,
                text="❌ Неподдерживаемый тип сообщения. Пересылка отменена."
            )
            return
        
        # Сохраняем информацию об авторе поста
        if author:
            post_authors[sent_message.message_id] = {
                'user_id': author.id,
                'username': author.username,
                'full_name': author.full_name
            }
            logger.info(f"Сохранен автор поста {sent_message.message_id}: {author.full_name}")
        
        # Отправляем подтверждение в группу
        await context.bot.send_message(
            chat_id=SOURCE_GROUP_ID,
            text="✅ Сообщение успешно переслано в канал!"
        )
        
        logger.info(f"Сообщение переслано в канал. Автор: {author.full_name if author else 'Неизвестный'}")
                
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await context.bot.send_message(
            chat_id=SOURCE_GROUP_ID,
            text=f"❌ Ошибка при пересылке сообщения: {str(e)}"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    user = query.from_user
    message = query.message
    
    try:
        data = query.data
        logger.info(f"Нажата кнопка: {data} от пользователя {user.full_name} (ID: {user.id})")
        
        if data.startswith('respond_no_username_'):
            # Кнопка для автора без username - показываем alert
            author_id = int(data.split('_')[3])
            
            await query.answer(
                text=f"❌ У автора нет username. Его ID: {author_id}",
                show_alert=True
            )
        
        elif data == 'respond_no_sender':
            await query.answer(
                text="❌ Не удалось определить автора сообщения",
                show_alert=True
            )
        
        elif data.startswith('cannot_'):
            # Кнопка "Не могу написать" - отправляем информацию о нажавшем автору поста
            if data == 'cannot_unknown':
                await query.answer(
                    text="❌ Не удалось определить автора сообщения",
                    show_alert=True
                )
                return
            
            author_id = int(data.split('_')[1])
            message_id = message.message_id
            
            # Получаем информацию об авторе поста из сохраненных данных
            author_info = post_authors.get(message_id)
            
            if not author_info:
                # Если не нашли в сохраненных, пробуем получить по ID
                try:
                    author_chat = await context.bot.get_chat(author_id)
                    author_info = {
                        'user_id': author_id,
                        'username': author_chat.username,
                        'full_name': author_chat.full_name
                    }
                except:
                    await query.answer(
                        text="❌ Не удалось найти автора поста",
                        show_alert=True
                    )
                    return
            
            # Формируем информацию о пользователе, который нажал кнопку
            user_info = f"👤 Пользователь {user.full_name}"
            if user.username:
                user_info += f" (@{user.username})"
            user_info += f"\n🆔 ID: {user.id}"
            
            # Отправляем информацию автору поста
            try:
                await context.bot.send_message(
                    chat_id=author_id,
                    text=f"❌ Пользователь не может вам написать!\n\n"
                         f"{user_info}\n\n"
                         f"Он пытался откликнуться на ваше объявление, но не может начать диалог. "
                         f"Свяжитесь с ним сами."
                )
                
                # Показываем уведомление нажавшему (сообщение в канале не меняется)
                await query.answer(
                    text="✅ Администратор уведомлен, ждите, скоро он вам напишет",
                    show_alert=True
                )
                
                logger.info(f"Информация о пользователе {user.id} отправлена автору {author_id}")
                
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение автору {author_id}: {e}")
                await query.answer(
                    text="❌ Не удалось уведомить администратора",
                    show_alert=True
                )
        
        elif data == 'owner':
            # Кнопка "Владелец" - ничего не делаем, она открывает чат через url
            pass
            
    except Exception as e:
        logger.error(f"Ошибка при обработке кнопки: {e}")
        await query.answer(
            text="❌ Произошла ошибка",
            show_alert=True
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "Бот запущен! Используйте /open в группе, чтобы переслать следующее сообщение в канал."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "Команды бота:\n"
        "/start - информация о боте\n"
        "/open - разрешить пересылку следующего сообщения из группы в канал\n"
        "/help - показать это сообщение\n\n"
        "После команды /open следующее сообщение в группе будет переслано в канал с кнопками."
    )

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик для всех типов сообщений из группы
    application.add_handler(
        MessageHandler(
            filters.Chat(SOURCE_GROUP_ID) & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL), 
            forward_to_channel
        )
    )
    
    # Обработчик для callback кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    print(f"Бот запущен... (ID группы: {SOURCE_GROUP_ID}, ID канала: {TARGET_CHANNEL_ID})")
    print("Нажмите Ctrl+C для остановки")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()