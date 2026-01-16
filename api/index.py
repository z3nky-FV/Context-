import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
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

# URL для отправки сообщений в Telegram (без aiogram)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ТВОЙ СТАРЫЙ ПРОМПТ
SYSTEM_PROMPT = (
    "Ты — ядро Context+. Твоя задача — извлечь смысл. "
    "Обязательно верни ответ СТРОГО в формате:\n"
    "TITLE: Название\n"
    "TYPE: Тип контента\n"
    "SUMMARY: 3 главных мысли\n"
    "TAGS: теги через запятую"
)

# --- БАЗА ---
def get_db_conn():
    return psycopg2.connect(POSTGRES_URL)

# --- ОТПРАВКА СООБЩЕНИЯ В TELEGRAM ---
def send_telegram_message(chat_id, text):
    try:
        requests.post(TELEGRAM_API_URL, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки в TG: {e}")

# --- AI ---
async def ask_openai(text):
    try:
        response = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Текст:\n{text[:5000]}"}
            ]
        )
        return response.choices[0].message.content
    except:
        return "TITLE: Ошибка\nSUMMARY: Сбой ИИ\nTAGS: error"

def parse_ai(text):
    data = {"TITLE": "...", "SUMMARY": "...", "TAGS": ""}
    for line in text.split('\n'):
        if "TITLE:" in line: data["TITLE"] = line.split("TITLE:")[1].strip()
        if "SUMMARY:" in line: data["SUMMARY"] = line.split("SUMMARY:")[1].strip()
        if "TAGS:" in line: data["TAGS"] = line.split("TAGS:")[1].strip()
    return data

# --- WEBHOOK ---
@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        
        # Проверяем, есть ли сообщение
        if "message" in data and "text" in data["message"]:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            text = msg["text"]
            user_id = msg["from"]["id"]

            if text.startswith("http"):
                # 1. Скрейпинг
                try:
                    r = requests.get(text, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                    soup = BeautifulSoup(r.text, 'html.parser')
                    raw_text = soup.get_text()
                except:
                    raw_text = "Сайт недоступен"

                # 2. OpenAI
                ai_res = await ask_openai(raw_text)
                parsed = parse_ai(ai_res)

                # 3. База
                conn = get_db_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO links (url, title, summary, tags, user_id) VALUES (%s, %s, %s, %s, %s)",
                    (text, parsed["TITLE"], parsed["SUMMARY"], parsed["TAGS"], user_id)
                )
                conn.commit()
                cur.close()
                conn.close()

                # 4. Ответ
                send_telegram_message(chat_id, f"✅ **{parsed['TITLE']}**\n\n_{parsed['SUMMARY']}_")
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error"}

# --- MINI APP ---
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