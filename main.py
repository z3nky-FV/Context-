import os
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
import psycopg2

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

def get_db_connection():
    return psycopg2.connect(POSTGRES_URL)

def get_site_info(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "Без названия"
        description = soup.find("meta", attrs={"name": "description"})
        summary = description["content"] if description else "Описание не найдено"
        return title, summary
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return None, None

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Присылай мне ссылки, и я сохраню их в твою личную базу Ghost Memory.")

@dp.message_handler()
async def handle_message(message: types.Message):
    if message.text.startswith("http"):
        url = message.text
        user_id = message.from_user.id
        title, summary = get_site_info(url)
        
        if title:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                # Сохраняем с user_id
                cur.execute(
                    "INSERT INTO links (url, title, summary, user_id) VALUES (%s, %s, %s, %s)",
                    (url, title, summary, user_id)
                )
                conn.commit()
                cur.close()
                conn.close()
                await message.answer(f"✅ Сохранено в твою базу:\n**{title}**", parse_mode="Markdown")
            except Exception as e:
                await message.answer(f"❌ Ошибка базы: {e}")
        else:
            await message.answer("❌ Не удалось прочитать сайт. Проверь ссылку.")

if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)