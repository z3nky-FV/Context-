<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Ghost Memory</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root { --bg: #050505; --accent: #6366f1; --border: rgba(255,255,255,0.08); }
        body { background: var(--bg); color: #fff; font-family: -apple-system, sans-serif; margin: 0; padding: 20px; overflow-x: hidden; }
        
        .glow { position: fixed; width: 300px; height: 300px; background: var(--accent); filter: blur(100px); opacity: 0.1; z-index: -1; top: -50px; right: -50px; border-radius: 50%; }
        
        .search-bar { position: sticky; top: 0; background: var(--bg); padding: 10px 0 20px 0; z-index: 10; }
        .search-bar input { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 12px; padding: 14px; color: #fff; outline: none; box-sizing: border-box; }
        
        .card { background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 18px; padding: 18px; margin-bottom: 12px; text-decoration: none; color: inherit; display: block; transition: 0.2s; }
        .card:active { transform: scale(0.98); background: rgba(255,255,255,0.05); }
        
        .card-title { font-size: 17px; font-weight: 700; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .card-desc { color: #888; font-size: 14px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        
        .empty { text-align: center; color: #444; margin-top: 60px; font-size: 15px; }
    </style>
</head>
<body>
    <div class="glow"></div>
    <div class="search-bar">
        <input type="text" placeholder="Поиск в памяти..." id="search">
    </div>

    <div id="links-container">
        {% if links %}
            {% for link in links %}
            <a href="{{ link.url }}" class="card">
                <div class="card-title">{{ link.title }}</div>
                <div class="card-desc">{{ link.summary }}</div>
            </a>
            {% endfor %}
        {% else %}
            <div class="empty">Здесь пока пусто... Пришли ссылку боту!</div>
        {% endif %}
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        tg.ready();

        // Изоляция пользователей через URL
        const params = new URLSearchParams(window.location.search);
        if (tg.initDataUnsafe.user && !params.has('user_id')) {
            window.location.search = `?user_id=${tg.initDataUnsafe.user.id}`;
        }

        // Живой поиск
        document.getElementById('search').oninput = (e) => {
            const query = e.target.value.toLowerCase();
            document.querySelectorAll('.card').forEach(card => {
                card.style.display = card.innerText.toLowerCase().includes(query) ? '' : 'none';
            });
        };
    </script>
</body>
</html>