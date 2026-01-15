import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

def get_db_connection():
    return psycopg2.connect(os.getenv("POSTGRES_URL"))

@app.get("/")
async def read_root(request: Request, user_id: int = None):
    links = []
    if user_id:
        try:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # Фильтруем по user_id
            cur.execute("SELECT * FROM links WHERE user_id = %s ORDER BY id DESC", (user_id,))
            links = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Ошибка DB: {e}")
    
    return templates.TemplateResponse("index.html", {"request": request, "links": links})