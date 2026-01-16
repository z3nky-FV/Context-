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

# Твои данные из .env
TOKEN = "8474212293:AAE_38E6VAqxX0jh6qt63uNeaU7rvfUOARY"
POSTGRES_URL = os.getenv("POSTGRES_URL") # Ссылку на Neon вставь в настройки Vercel!
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ПРОМПТ
SYSTEM_PROMPT = "Ты — ядро Context+. Верни ответ СТРОГО в формате: TITLE: Название\nSUMMARY: 3 мысли\nTAGS: теги"

@app.post(f"/api/webhook/{TOKEN}")
async def bot_webhook(request: Request):
    try:
        data = await request.json()
        if "message" in data and "text" in data["message"]:
            msg = data["message"]
            chat_id = msg["chat"]["id"]
            url = msg["text"]
            
            if url.startswith("http"):
                # Парсинг
                res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # OpenAI
                response = await ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": soup.get_text()[:4000]}]
                )
                ai_res = response.choices[0].message.content

                # База (Используем только Neon!)
                conn = psycopg2.connect(POSTGRES_URL)
                cur = conn.cursor()
                cur.execute("INSERT INTO links (url, title, summary) VALUES (%s, %s, %s)", (url, "Сайт", ai_res))
                conn.commit()
                cur.close()
                conn.close()

                # Ответ
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
                    "chat_id": chat_id, "text": f"✅ Сохранено!\n{ai_res}"
                })
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/")
async def index(request: Request):
    links = []
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM links ORDER BY id DESC LIMIT 10")
        links = cur.fetchall()
        cur.close()
        conn.close()
    except: pass
    return templates.TemplateResponse("index.html", {"request": request, "links": links})