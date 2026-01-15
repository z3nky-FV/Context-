import asyncio
import os
import re
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
import requests
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
import asyncpg
from dotenv import load_dotenv

# Загрузка настроек
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

# --- ФУНКЦИИ ИИ ---

async def get_ai_analysis(raw_text):
    """Тот самый промпт: TITLE, TYPE, SUMMARY, TAGS"""
    prompt = (
        "Ты — ядро Context+. Твоя задача — извлечь смысл. "
        "Обязательно верни ответ СТРОГО в формате:\n"
        "TITLE: Название\n"
        "TYPE: Тип контента\n"
        "SUMMARY: 3 главных мысли\n"
        "TAGS: теги через запятую"
    )
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Данные сайта:\n\n{raw_text[:5000]}"}
            ]
        )
        res = response.choices[0].message.content
        
        # Парсинг строк
        data = {"TITLE": "Без названия", "SUMMARY": "Нет описания", "TAGS": ""}
        for line in res.split('\n'):
            if line.startswith("TITLE:"): data["TITLE"] = line.replace("TITLE:", "").strip()
            if line.startswith("SUMMARY:"): data["SUMMARY"] = line.replace("SUMMARY:", "").strip()
            if line.startswith("TAGS:"): data["TAGS"] = line.replace("TAGS:", "").strip()
        return data
    except Exception as e:
        logging.error(f"Ошибка OpenAI: {e}")
        return None

# --- РАБОТА С БАЗОЙ ---

async def save_to_db(url, title, summary, tags):
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute(
            "INSERT INTO links (url, title, summary, tags) VALUES ($1, $2, $3, $4)",
            url, title, summary, tags
        )
        await conn.close()
        return True
    except Exception as e:
        logging.error(f"Ошибка БД: {e}")
        return False

# --- ОБРАБОТЧИКИ ---

@dp.message(F.text.regexp(r'https?://\S+'))
async def handle_link(message: Message):
    url = re.search(r'https?://\S+', message.text).group(0)
    temp_msg = await message.answer("🔄 Анализирую (OpenAI)...")

    try:
        res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, 'html.parser')
        content = soup.get_text()

        analysis = await get_ai_analysis(content)
        if analysis:
            success = await save_to_db(url, analysis["TITLE"], analysis["SUMMARY"], analysis["TAGS"])
            if success:
                await temp_msg.edit_text(
                    f"✅ **Сохранено!**\n\n**{analysis['TITLE']}**\n_{analysis['SUMMARY']}_", 
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await temp_msg.edit_text("❌ Ошибка базы данных.")
    except Exception as e:
        await temp_msg.edit_text(f"❌ Ошибка: {e}")

async def main():
    print("Бот запущен (OpenAI + Polling)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())