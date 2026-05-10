from telegram.ext import Application, CommandHandler, MessageHandler, filters
import telegram.error
import speech_recognition as sr
from pydub import AudioSegment
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"Starting dummy server on port {port}...")
    server.serve_forever()
recognizer = sr.Recognizer()

def format_text(text_chunks):
    formatted_text = ""
    for chunk in text_chunks:
        if not chunk:
            continue
        words = chunk.split()
        sentences = []
        current_sentence = []
        
        for i, word in enumerate(words):
            current_sentence.append(word)
            if i + 1 < len(words) and words[i + 1][0].isupper():
                sentences.append(" ".join(current_sentence))
                current_sentence = []
        
        if current_sentence:
            sentences.append(" ".join(current_sentence))
        
        formatted_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence.endswith(('.', '!', '?')):
                sentence += '.'
            formatted_chunk += sentence + " "
        
        formatted_chunk = formatted_chunk[0].upper() + formatted_chunk[1:].strip()
        formatted_text += formatted_chunk + "\n\n"
    
    return formatted_text.strip()

async def start(update, context):
    await update.message.reply_text('Бот запущено! Надішли мені голосове повідомлення, MP3, WAV або MP4 файл.')

async def handle_audio(update, context):
    message = update.message
    
    if message.voice:
        file_id = message.voice.file_id
        file_size = message.voice.file_size
        mime_type = 'audio/ogg'
        source = 'голосове'
    elif message.audio and message.audio.mime_type in ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave']:
        file_id = message.audio.file_id
        file_size = message.audio.file_size
        mime_type = message.audio.mime_type
        source = 'аудіо'
    elif message.document and message.document.mime_type in ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 'video/mp4']:
        file_id = message.document.file_id
        file_size = message.document.file_size
        mime_type = message.document.mime_type
        source = 'документ'
    elif message.video and message.video.mime_type == 'video/mp4':
        file_id = message.video.file_id
        file_size = message.video.file_size
        mime_type = message.video.mime_type
        source = 'відео'
    elif message.video_note:
        file_id = message.video_note.file_id
        file_size = message.video_note.file_size
        mime_type = 'video/mp4'
        source = 'відеопримітка'
    else:
        return

    #await update.message.reply_text(f"Отримано {source} повідомлення (MP3/WAV/MP4), обробляю...")

    try:
        file = await context.bot.get_file(file_id)
        await file.download_to_drive('audio_file_temp')
    except Exception as e:
        await update.message.reply_text(f"Помилка під час завантаження файлу: {e}")
        return

    try:
        if mime_type == 'audio/ogg':
            audio = AudioSegment.from_ogg('audio_file_temp')
        elif mime_type in ['audio/mpeg', 'audio/mp3']:
            audio = AudioSegment.from_mp3('audio_file_temp')
        elif mime_type in ['audio/wav', 'audio/wave']:
            audio = AudioSegment.from_wav('audio_file_temp')
        elif mime_type == 'video/mp4':
            audio = AudioSegment.from_file('audio_file_temp', format='mp4')
        else:
            await update.message.reply_text('Непідтримуваний формат файлу.')
            return

        if file_size > 1_048_576:
            chunk_length = 30000
            chunks = [audio[i:i + chunk_length] for i in range(0, len(audio), chunk_length)]
        else:
            chunks = [audio]

        text_chunks = []
        for i, chunk in enumerate(chunks):
            chunk.export(f'audio_chunk_{i}.wav', format='wav')
            with sr.AudioFile(f'audio_chunk_{i}.wav') as source_file:
                audio_data = recognizer.record(source_file)
                try:
                    text = recognizer.recognize_google(audio_data, language='uk-UA')
                    text_chunks.append(text)
                except sr.UnknownValueError:
                    text_chunks.append("[Не вдалося розпізнати частину]")
                except sr.RequestError as e:
                    await update.message.reply_text(f'Помилка сервісу розпізнавання: {e}')
                    return
            os.remove(f'audio_chunk_{i}.wav')

        full_text = format_text(text_chunks)
        await update.message.reply_text(f'У повідомленні:\n{full_text}')

    except Exception as e:
        await update.message.reply_text(f'Виникла помилка під час обробки: {e}')
    
    finally:
        if os.path.exists('audio_file_temp'):
            os.remove('audio_file_temp')
        if os.path.exists('audio_file_temp.wav'):
            os.remove('audio_file_temp.wav')

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

    # Запускаем фиктивный сервер в фоновом потоке
    server_thread = threading.Thread(target=run_dummy_server)
    server_thread.daemon = True
    server_thread.start()

    application = Application.builder().token(token).build()
    application.add_handler(MessageHandler(
        (filters.ChatType.PRIVATE | filters.ChatType.GROUPS) & (filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.VIDEO | filters.VIDEO_NOTE),
        handle_audio
    ))
    application.add_handler(CommandHandler("start", start))
    print("Бот запущено...")
    application.run_polling()

if __name__ == '__main__':
    main()
