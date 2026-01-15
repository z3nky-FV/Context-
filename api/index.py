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

@app.get("/")
async def index(request: Request, user_id: int = None):
    links = []
    if user_id:
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM links WHERE user_id = %s ORDER BY id DESC", (user_id,))
            links = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DATABASE ERROR: {e}")
    return templates.TemplateResponse("index.html", {"request": request, "links": links})

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat.id
            user_id = update.message.from_user.id

            if text.startswith("http"):
                # Попытка парсинга
                try:
                    res = requests.get(text, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                    soup = BeautifulSoup(res.text, 'html.parser')
                    title = soup.title.string if soup.title else text
                except:
                    title = text
                
                # Попытка записи в базу
                conn = psycopg2.connect(POSTGRES_URL)
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO links (url, title, summary, user_id) VALUES (%s, %s, %s, %s)",
                    (text, title, "Сохранено", user_id)
                )
                conn.commit()
                cur.close()
                conn.close()
                
                await bot.send_message(chat_id, f"✅ Сохранено: {title}")
            elif text == "/start":
                await bot.send_message(chat_id, "Бот на Vercel готов!")

        return {"status": "ok"}
    except Exception as e:
        # Эта строчка выведет реальную причину ошибки 500 в логи Vercel
        print(f"CRITICAL ERROR: {e}")
        return {"status": "error", "message": str(e)}