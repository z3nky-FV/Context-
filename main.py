import asyncio
import os
import re
import requests
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
import asyncpg
from dotenv import load_dotenv
import trafilatura
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

load_dotenv()
# Используем URL из Vercel (обязательно добавь sslmode=require если его нет в конце)
DATABASE_URL = os.getenv("POSTGRES_URL") 
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_page_content(url):
    # Маскируемся под реального человека, чтобы Nike не блокировал
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        # Пробуем достать статью
        text = trafilatura.extract(response.text)
        if text and len(text) > 400: return text
        
        # Если это магазин, достаем описание вручную
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else ""
        desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
        desc_text = desc.get("content", "") if desc else ""
        return f"Заголовок: {title}. Описание: {desc_text}"
    except: return None

async def get_ai_analysis(raw_text):
    # Улучшенный промпт, чтобы не было "говно-ответов"
    prompt = (
        "Ты — аналитик. Твоя задача — извлечь СУТЬ.\n"
        "1. Если это магазин, пиши: 'Официальный сайт [Бренд]. Специализация: [категория товаров]'.\n"
        "2. ИГНОРИРУЙ рекламные слова (SPOTLIGHT, Just Do It, Sale).\n"
        "3. Если статья — выдели 2 главных факта.\n"
        "Верни ответ СТРОГО:\nTITLE: Название\nSUMMARY: Суть (2 предложения)\nTAGS: тег1, тег2"
    )
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": raw_text[:5000]}]
        )
        res = response.choices[0].message.content
        data = {"TITLE": "Без названия", "SUMMARY": "Нет данных", "TAGS": ""}
        for line in res.split('\n'):
            if line.startswith("TITLE:"): data["TITLE"] = line.replace("TITLE:", "").strip()
            if line.startswith("SUMMARY:"): data["SUMMARY"] = line.replace("SUMMARY:", "").strip()
            if line.startswith("TAGS:"): data["TAGS"] = line.replace("TAGS:", "").strip()
        return data
    except: return None

@dp.message(F.text.regexp(r'https?://\S+'))
async def handle_link(message: Message):
    url = re.search(r'https?://\S+', message.text).group(0)
    msg = await message.answer("🔄 Анализирую ссылку...")
    
    try:
        content = await asyncio.to_thread(get_page_content, url)
        analysis = await get_ai_analysis(content) if content else None
        
        if analysis:
            if not DATABASE_URL:
                raise ValueError("POSTGRES_URL не найден. Проверьте .env")

            conn = await asyncpg.connect(DATABASE_URL)
            await conn.execute(
                "INSERT INTO links (user_id, chat_id, url, title, summary, tags) VALUES ($1, $2, $3, $4, $5, $6)",
                message.from_user.id, message.chat.id, url, analysis["TITLE"], analysis["SUMMARY"], analysis["TAGS"].split(',')
            )
            await conn.close()
            await msg.edit_text(f"✅ **Сохранено!**\n{analysis['TITLE']}", parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.edit_text("❌ Не удалось прочитать сайт.")
    except Exception as e:
        await msg.edit_text(f"⚠️ Ошибка: {str(e)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())