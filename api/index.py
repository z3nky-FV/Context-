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

# Берём переменные, которые ты настроишь в Vercel
TOKEN = os.getenv("BOT_TOKEN")
POSTGRES_URL = os.getenv("POSTGRES_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = (
    "Ты — ядро Context+. Твоя задача — извлечь смысл. "
    "Обязательно верни ответ СТРОГО в формате:\n"
    "TITLE: Название\n"
    "TYPE: Тип контента\n"
    "SUMMARY: 3 главных мысли\n"
    "TAGS: теги через запятую"
)

def get_db_conn():
    # Используем именно ту ссылку из Neon, что на твоём скрине
    return psycopg2.connect(POSTGRES_URL)

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        if "message" in data and "text" in data["message"]:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            url = msg["text"]
            
            if url.startswith("http"):
                # Парсим сайт
                res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, 'html.parser')
                page_text = soup.get_text()[:4000]

                # OpenAI
                response = await ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": page_text}]
                )
                ai_text = response.choices[0].message.content

                # Парсинг ответа
                p = {"TITLE": "...", "SUMMARY": "...", "TAGS": ""}
                for line in ai_text.split('\n'):
                    if "TITLE:" in line: p["TITLE"] = line.split("TITLE:")[1].strip()
                    if "SUMMARY:" in line: p["SUMMARY"] = line.split("SUMMARY:")[1].strip()
                    if "TAGS:" in line: p["TAGS"] = line.split("TAGS:")[1].strip()

                # Сохраняем в Neon
                conn = get_db_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO links (url, title, summary, tags) VALUES (%s, %s, %s, %s)",
                    (url, p["TITLE"], p["SUMMARY"], p["TAGS"])
                )
                conn.commit()
                cur.close()
                conn.close()

                # Отправка в телегу
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
                    "chat_id": chat_id, 
                    "text": f"✅ **{p['TITLE']}**\n\n_{p['SUMMARY']}_", 
                    "parse_mode": "Markdown"
                })
        return {"ok": True}
    except Exception as e:
        print(f"Error: {e}")
        return {"ok": False}

@app.get("/")
async def index(request: Request):
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM links ORDER BY id DESC LIMIT 10")
        links = cur.fetchall()
        cur.close()
        conn.close()
    except: links = []
    return templates.TemplateResponse("index.html", {"request": request, "links": links})