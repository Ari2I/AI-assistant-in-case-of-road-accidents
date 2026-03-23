# База данных


# Установка и запуск
Для установки зависимостей можно ввести команды

cd backend
pip install -r requirements.txt

Или нажать в проводнике на файл ins.bat или использовать команду ins.bat для установки виртуального окружения, его
запуска, установки в него зависимостей и деактивации

Для активации нажать в проводнике на файл act.bat или использовать команду act.bat для запуска виртуального окружения
запуска файла create_db.py и деактивации виртуального окружения

Для того, чтобы использовать в терминале PyCharm команды ins.bat или act.bat нужно в File → settings → Terminal →
Shell path выбрать файл cmd вместо powershell



# Настройка переменных окружения
Скопируйте .env.example (если есть) или создайте .env вручную:
```env
    # Подключение к PostgreSQL
    DB_HOST=localhost
    DB_PORT=5432
    DB_NAME=postgres          # Существующая БД для создания новой
    DB_USER=postgres
    DB_PASSWORD=your_password
    # Имя новой базы данных проекта
    NEW_DB_NAME=my_database
    
    # (Опционально) Настройки для будущего API
    API_HOST=127.0.0.1
    API_PORT=8000
```
⚠️ Важно: Добавьте .env в .gitignore — не коммитьте пароли в репозиторий!



# Создание базы данных
python create_db.py



# Взаимодействие с базой данных
1. Раскоментируйте необходимые функции или добавьте существующие в функцию run_migration 
2. Запустите с помощью команды python migrate_db.py



# 🔧 Как расширять функционал / Добавление новых таблиц
1. Откройте create_db.py
2. Найдите функцию create_tables()
3. Добавьте новый CREATE TABLE запрос:

cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        product_id INTEGER REFERENCES products(id),
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
Не забудьте conn.commit()



# Функционал управления данными
1. create_user()
Добавление нового пользователя
✅ Да
2. get_all_users()
Получение всех записей
✅ Да
3. get_user_by_id()
Поиск по ID
✅ Да
4. get_user_by_email()
Поиск по email
✅ Да
5. update_user()
Обновление данных
✅ Да
6. delete_user()
Удаление по ID
✅ Да
7. count_users()
Подсчёт записей
✅ Да
8. clear_all_users()
Очистка всей таблицы



# Использование db_queries.py в веб-приложении (Flask пример)
```python
from flask import Flask, request, jsonify
from db_queries import create_user, get_all_users, delete_user

app = Flask(__name__)

@app.route('/users', methods=['POST'])
def add_user():
    data = request.json
    user_id = create_user(data['name'], data['email'])
    return jsonify({'id': user_id}), 201

@app.route('/users', methods=['GET'])
def list_users():
    users = get_all_users()
    return jsonify(users)

@app.route('/users/<int:user_id>', methods=['DELETE'])
def remove_user(user_id):
    delete_user(user_id)
    return '', 204
```
🔒 Важные особенности
1. Параметризованные запросы — все запросы используют %s для защиты от SQL-инъекций
2. Обработка ошибок — каждый запрос обёрнут в try/except
3. Транзакции — используется commit() и rollback() для целостности данных
4. RealDictCursor — результаты возвращаются как словари для удобства



# 👨‍💻 Для бекэнд-разработчика 📌 Интеграция в проект / Запуск при развёртывании

1. Создайте базу данных с помощью файла create_db.py
2. Для добавления новых таблиц используйте файл edit_database
3. После инициализации подключайтесь к базе данных NEW_DB_NAME для работы с таблицей users.
🔧 Пример подключения в коде:
```python
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database=os.getenv('NEW_DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cursor = conn.cursor()
```
