import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from aiogram import Bot, Dispatcher, types
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Настройки
app = FastAPI()
templates = Jinja2Templates(directory="templates")
TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Вспомогательные функции
def get_db_conn():
    return psycopg2.connect(POSTGRES_URL)

def get_site_info(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else "Без названия"
        return title, "Сохранено из Telegram"
    except:
        return None, None

# --- ЧАСТЬ 1: ВЕБ-ИНТЕРФЕЙС (MINI APP) ---
@app.get("/")
async def index(request: Request, user_id: int = None):
    links = []
    if user_id:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM links WHERE user_id = %s ORDER BY id DESC", (user_id,))
        links = cur.fetchall()
        cur.close()
        conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "links": links})

# --- ЧАСТЬ 2: ЛОГИКА БОТА (WEBHOOK) ---
@app.post(f"/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    update = await request.json()
    update_obj = types.Update(**update)
    
    if update_obj.message and update_obj.message.text:
        msg = update_obj.message
        if msg.text.startswith("http"):
            title, summary = get_site_info(msg.text)
            if title:
                conn = get_db_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO links (url, title, summary, user_id) VALUES (%s, %s, %s, %s)",
                    (msg.text, title, summary, msg.from_user.id)
                )
                conn.commit()
                cur.close()
                conn.close()
                await bot.send_message(msg.chat.id, f"✅ Сохранено: {title}")
            else:
                await bot.send_message(msg.chat.id, "❌ Не удалось прочитать сайт.")
        elif msg.text == "/start":
            await bot.send_message(msg.chat.id, "Привет! Я работаю на Vercel 24/7. Присылай ссылку!")
            
    return {"status": "ok"}