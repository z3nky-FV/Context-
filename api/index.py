import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from aiogram import Bot, Dispatcher, types
from openai import AsyncOpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ТОТ САМЫЙ ПРОМТ
SYSTEM_PROMPT = (
    "Ты — ядро Context+. Твоя задача — извлечь смысл. "
    "Обязательно верни ответ СТРОГО в формате:\n"
    "TITLE: Название\n"
    "TYPE: Тип контента\n"
    "SUMMARY: 3 главных мысли\n"
    "TAGS: теги через запятую"
)

def get_db_conn():
    return psycopg2.connect(POSTGRES_URL)

async def ask_openai(text):
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Данные сайта:\n\n{text[:5000]}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"TITLE: Ошибка\nSUMMARY: {str(e)}\nTAGS: ошибка"

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    update_data = await request.json()
    update = types.Update(**update_data)
    
    if update.message and update.message.text:
        msg = update.message
        if msg.text.startswith("http"):
            # Скрейпинг
            res = requests.get(msg.text, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(res.text, 'html.parser')
            content = soup.get_text()

            # Анализ через OpenAI
            ai_res = await ask_openai(content)
            
            # Парсинг
            data = {"TITLE": "Без названия", "SUMMARY": "Нет описания", "TAGS": ""}
            for line in ai_res.split('\n'):
                if line.startswith("TITLE:"): data["TITLE"] = line.replace("TITLE:", "").strip()
                if line.startswith("SUMMARY:"): data["SUMMARY"] = line.replace("SUMMARY:", "").strip()
                if line.startswith("TAGS:"): data["TAGS"] = line.replace("TAGS:", "").strip()

            # Сохранение
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO links (url, title, summary, tags) VALUES (%s, %s, %s, %s)",
                (msg.text, data["TITLE"], data["SUMMARY"], data["TAGS"])
            )
            conn.commit()
            cur.close()
            conn.close()
            
            await bot.send_message(msg.chat.id, f"✅ Сохранено!\n\n**{data['TITLE']}**", parse_mode="Markdown")
            
    return {"status": "ok"}

@app.get("/")
async def read_root(request: Request):
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM links ORDER BY id DESC")
    links = cur.fetchall()
    cur.close()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "links": links})