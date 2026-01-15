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

# Все ключи должны быть прописаны в Settings -> Environment Variables на Vercel!
TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Твой ключ для ИИ

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

def get_db_conn():
    return psycopg2.connect(POSTGRES_URL, connect_timeout=10)

# ТОТ САМЫЙ ПРОМТ ДЛЯ ИИ
def ask_ai_summary(text):
    if not GEMINI_API_KEY:
        return "Краткое описание недоступно (нет ключа ИИ)"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{
                "text": f"Сделай очень краткое саммари (1-2 предложения) этого текста на русском языке: {text}"
            }]
        }]
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Не удалось создать описание через ИИ"

def get_site_info(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.title.string if soup.title else url
        
        # Берем текст со страницы для ИИ
        page_text = soup.get_text()[:2000] 
        summary = ask_ai_summary(page_text)
        
        return title.strip(), summary.strip()
    except:
        return url, "Сайт недоступен для анализа"

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

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        update_data = await request.json()
        update = types.Update(**update_data)
        if update.message and update.message.text:
            msg = update.message
            if msg.text.startswith("http"):
                # Использование ИИ для анализа
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
                await bot.send_message(msg.chat.id, f"✅ Сохранено с помощью ИИ:\n\n**{title}**\n\n_{summary}_", parse_mode="Markdown")
        return {"status": "ok"}
    except Exception as e:
        print(f"Ошибка: {e}")
        return {"status": "error"}