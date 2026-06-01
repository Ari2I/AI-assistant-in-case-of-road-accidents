#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест распознавания фото документа через GigaChat.
Файл загружается → модель отвечает → файл УДАЛЯЕТСЯ.
"""

import os
from langchain_gigachat import GigaChat
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from rag.file_handler import delete_file

# 1. Загружаем токен
load_dotenv()
GIGA_AUTH = os.getenv("GIGA_AUTH") or os.getenv("GIGACHAT_CREDENTIALS")

if not GIGA_AUTH:
    print("❌ Токен не найден. Проверь файл .env")
    exit()

# 2. Создаём клиент (как в твоём проекте)
llm = GigaChat(
    credentials=GIGA_AUTH,
    verify_ssl_certs=False,
    scope="GIGACHAT_API_B2B",
    model="GigaChat-2-Pro",  # важно: мультимодальная модель
)

# 3. Укажи путь к тестовому фото (ЗАМЕНИ НА СВОЁ!)
PHOTO_PATH = "doc.jpg"   # если файл называется doc.jpg и лежит в папке проекта

if not os.path.exists(PHOTO_PATH):
    print(f"❌ Файл {PHOTO_PATH} не найден.")
    print("Создай или скопируй фото в папку проекта и назови doc.jpg")
    exit()

# 4. Загружаем файл
print(f"📁 Загружаем {PHOTO_PATH}...")
with open(PHOTO_PATH, "rb") as f:
    uploaded = llm.upload_file((PHOTO_PATH, f.read()), purpose="general")

file_id = uploaded.id_
print(f"✅ Загружен, ID: {file_id}")

# 5. Отправляем запрос с фото
print("🤖 Спрашиваем модель...")
msg = HumanMessage(
    content_blocks=[
        {"type": "text", "text": "Опиши, что написано в этом документе. Выдели все цифры, даты, ФИО, серии и номера."},
        {"type": "image", "file_id": file_id},
    ]
)

response = llm.invoke([msg])
print("\n📄 ОТВЕТ МОДЕЛИ:\n")
print(response.content)
print("\n" + "="*50)

# 6. Удаляем файл — ОБЯЗАТЕЛЬНО!
print(f"🗑️ Удаляем файл {file_id}...")
delete_file(llm, file_id)

print("✅ Тест завершён. Файл удалён.")