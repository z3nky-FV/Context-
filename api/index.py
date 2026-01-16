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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POSTGRES_URL = os.getenv("POSTGRES_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
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
    return psycopg2.connect(POSTGRES_URL)

async def analyze_link(url):
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text()[:5000]
        res = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"TITLE: Ошибка\nSUMMARY: {str(e)}\nTAGS: error"

def parse_res(res_text):
    data = {"title": "Без названия", "summary": "Нет описания", "tags": ""}
    for line in res_text.split('\n'):
        if "TITLE:" in line: data["title"] = line.replace("TITLE:", "").strip()
        if "SUMMARY:" in line: data["summary"] = line.replace("SUMMARY:", "").strip()
        if "TAGS:" in line: data["tags"] = line.replace("TAGS:", "").strip()
    return data

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Бот Context+ готов. Скидывай ссылку!")

@dp.message_handler()
async def handle_message(message: types.Message):
    if message.text.startswith("http"):
        waiting_msg = await message.answer("🔍 Анализирую...")
        raw_res = await analyze_link(message.text)
        parsed = parse_res(raw_res)
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO links (url, title, summary, tags, user_id) VALUES (%s, %s, %s, %s, %s)",
                (message.text, parsed["title"], parsed["summary"], parsed["tags"], message.from_user.id)
            )
            conn.commit()
            cur.close()
            conn.close()
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=waiting_msg.message_id,
                text=f"✅ **{parsed['title']}**\n\n{parsed['summary']}\n\n#{parsed['tags']}",
                parse_mode="Markdown"
            )
        except Exception as e:
            await message.answer(f"Ошибка БД: {e}")

@app.post(f"/api/webhook/{TOKEN}")
async def webhook_endpoint(request: Request):
    update_data = await request.json()
    update = types.Update(**update_data)
    Dispatcher.set_current(dp)
    Bot.set_current(bot)
    await dp.process_update(update)
    return {"ok": True}

@app.get("/")
async def index(request: Request, user_id: int = None):
    links = []
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if user_id:
            cur.execute("SELECT * FROM links WHERE user_id = %s ORDER BY id DESC", (user_id,))
        else:
            cur.execute("SELECT * FROM links ORDER BY id DESC LIMIT 20")
        links = cur.fetchall()
        cur.close()
        conn.close()
    except: pass
    return templates.TemplateResponse("index.html", {"request": request, "links": links})