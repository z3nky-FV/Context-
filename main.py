import logging
from aiogram import executor
from api.index import dp

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    print("Запуск бота локально...")
    executor.start_polling(dp, skip_updates=True)