import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from aiogram import Bot, types
from openai import AsyncOpenAI
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=TOKEN)
# Инициализация OpenAI
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# --- ТВОЙ СТАРЫЙ ПРОМПТ ---
SYSTEM_PROMPT = (
    "Ты — ядро Context+. Твоя задача — извлечь смысл. "
    "Обязательно верни ответ СТРОГО в формате:\n"
    "TITLE: Название\n"
    "TYPE: Тип контента\n"
    "SUMMARY: 3 главных мысли\n"
    "TAGS: теги через запятую"
)

# --- БАЗА ДАННЫХ ---
def get_db_conn():
    return psycopg2.connect(POSTGRES_URL)

# --- ЛОГИКА ИИ ---
async def ask_openai_analysis(text):
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Текст сайта:\n\n{text[:6000]}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка OpenAI: {e}")
        return "TITLE: Ошибка\nSUMMARY: Не удалось обработать\nTAGS: error"

def parse_ai_response(ai_text):
    data = {"TITLE": "...", "SUMMARY": "...", "TAGS": ""}
    for line in ai_text.split('\n'):
        if "TITLE:" in line: data["TITLE"] = line.split("TITLE:")[1].strip()
        if "SUMMARY:" in line: data["SUMMARY"] = line.split("SUMMARY:")[1].strip()
        if "TAGS:" in line: data["TAGS"] = line.split("TAGS:")[1].strip()
    return data

# --- WEBHOOK (Бот) ---
@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        
        if update.message and update.message.text:
            msg = update.message
            if msg.text.startswith("http"):
                # 1. Скрейпинг
                try:
                    r = requests.get(msg.text, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                    soup = BeautifulSoup(r.text, 'html.parser')
                    raw_text = soup.get_text()
                except:
                    raw_text = "Текст недоступен"

                # 2. Анализ OpenAI
                ai_raw = await ask_openai_analysis(raw_text)
                parsed = parse_ai_response(ai_raw)

                # 3. Сохранение в БД (с тегами и user_id)
                conn = get_db_conn()
                cur = conn.cursor()
                # Убедись, что в базе есть колонка tags! Если нет - убери её из запроса ниже
                cur.execute(
                    "INSERT INTO links (url, title, summary, tags, user_id) VALUES (%s, %s, %s, %s, %s)",
                    (msg.text, parsed["TITLE"], parsed["SUMMARY"], parsed["TAGS"], msg.from_user.id)
                )
                conn.commit()
                cur.close()
                conn.close()

                # 4. Ответ пользователю
                await bot.send_message(
                    msg.chat.id, 
                    f"✅ **{parsed['TITLE']}**\n\n_{parsed['SUMMARY']}_\n\n#{parsed['TAGS']}", 
                    parse_mode="Markdown"
                )
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}

# --- MINI APP (Сайт) ---
@app.get("/")
async def index(request: Request, user_id: int = None):
    links = []
    if user_id:
        try:
            conn = get_db_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM links WHERE user_id = %s ORDER BY id DESC", (user_id,))
            links = cur.fetchall()
            cur.close()
            conn.close()
        except: pass
    return templates.TemplateResponse("index.html", {"request": request, "links": links})