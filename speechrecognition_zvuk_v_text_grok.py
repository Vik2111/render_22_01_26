from telegram.ext import Application, CommandHandler, MessageHandler, filters
import telegram.error
import speech_recognition as sr
from pydub import AudioSegment
import os

# Инициализация распознавателя речи
recognizer = sr.Recognizer()

# Функция для форматирования текста с пунктуацией и абзацами
def format_text(text_chunks):
    formatted_text = ""
    for chunk in text_chunks:
        if chunk:  # Проверяем, что кусок не пустой
            # Добавляем точку в конце фразы, если её нет, и делаем первую букву заглавной
            chunk = chunk.strip()
            if not chunk.endswith(('.', '!', '?')):
                chunk += '.'
            chunk = chunk[0].upper() + chunk[1:]
            formatted_text += chunk + "\n\n"  # Добавляем абзац после каждой части
    return formatted_text.strip()

# Функция для начала работы бота
async def start(update, context):
    await update.message.reply_text('Бот запущен! Отправь мне голосовое сообщение или MP3 файл.')

# Функция для обработки голосовых сообщений и MP3
async def handle_audio(update, context):
    message = update.message
    
    # Проверяем тип сообщения
    if message.voice:
        file_id = message.voice.file_id
        file_size = message.voice.file_size  # Размер в байтах
        is_voice = True
    elif message.audio and message.audio.mime_type in ['audio/mpeg', 'audio/mp3']:
        file_id = message.audio.file_id
        file_size = message.audio.file_size
        is_voice = False
    elif message.document and message.document.mime_type in ['audio/mpeg', 'audio/mp3']:
        file_id = message.document.file_id
        file_size = message.document.file_size
        is_voice = False
    else:
        await update.message.reply_text('Пожалуйста, отправь голосовое сообщение или MP3.')
        return

    await update.message.reply_text("Получено голосовое сообщение (MP3), обрабатываю...")

    # Скачиваем файл
    try:
        file = await context.bot.get_file(file_id)
        await file.download_to_drive('audio_file_temp')
    except Exception as e:
        await update.message.reply_text(f"Ошибка при загрузке файла: {e}")
        return

    try:
        # Загружаем аудио
        if is_voice:
            audio = AudioSegment.from_ogg('audio_file_temp')
        else:
            try:
                audio = AudioSegment.from_mp3('audio_file_temp')
            except Exception:
                audio = AudioSegment.from_wav('audio_file_temp')

        # Проверяем размер файла (1 МБ = 1_048_576 байт)
        if file_size > 1_048_576:  # Если больше 1 МБ
            # Разрезаем на части по 30 секунд (30000 мс)
            chunk_length = 30000  # 30 секунд в миллисекундах
            chunks = [audio[i:i + chunk_length] for i in range(0, len(audio), chunk_length)]
        else:
            chunks = [audio]  # Если меньше 1 МБ, обрабатываем целиком

        # Обрабатываем каждую часть
        text_chunks = []
        for i, chunk in enumerate(chunks):
            chunk.export(f'audio_chunk_{i}.wav', format='wav')
            with sr.AudioFile(f'audio_chunk_{i}.wav') as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data, language='ru-RU')
                    text_chunks.append(text)
                except sr.UnknownValueError:
                    text_chunks.append("[Не удалось распознать часть]")
                except sr.RequestError as e:
                    await update.message.reply_text(f'Ошибка сервиса распознавания: {e}')
                    return
            os.remove(f'audio_chunk_{i}.wav')

        # Форматируем текст с пунктуацией и абзацами
        full_text = format_text(text_chunks)

        # Отправляем полный текст
        await update.message.reply_text(f'Расшифрованный текст:\n{full_text}')

    except Exception as e:
        await update.message.reply_text(f'Произошла ошибка при обработке: {e}')
    
    finally:
        # Удаляем временные файлы
        if os.path.exists('audio_file_temp'):
            os.remove('audio_file_temp')
        if os.path.exists('audio_file_temp.wav'):
            os.remove('audio_file_temp.wav')

# Основная функция
def main():
    application = Application.builder().token("5921945646:AAGjTmhh83nswhXNjYloN8k_96FFdAVjbbI").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.VOICE | filters.AUDIO | filters.Document.ALL),
        handle_audio
    ))
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
