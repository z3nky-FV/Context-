from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import asyncpg
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    conn = await asyncpg.connect(os.getenv("POSTGRES_URL"))
    rows = await conn.fetch("SELECT title, summary, url, tags FROM links ORDER BY id DESC")
    await conn.close()
    
    links = [dict(row) for row in rows]
    return templates.TemplateResponse("index.html", {"request": request, "links": links})