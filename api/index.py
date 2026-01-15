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

app = FastAPI()
templates = Jinja2Templates(directory="templates")

TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

def get_db_conn():
    return psycopg2.connect(POSTGRES_URL, connect_timeout=10)

def get_site_info(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else url
        return title.strip(), "Сохранено из Telegram"
    except:
        return url, "Описание недоступно"

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
        except Exception as e:
            print(f"DB Error: {e}")
    return templates.TemplateResponse("index.html", {"request": request, "links": links})

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        if update.message and update.message.text:
            msg = update.message
            if msg.text.startswith("http"):
                title, summary = get_site_info(msg.text)
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
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "error"}