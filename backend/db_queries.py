import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os


load_dotenv()


def get_connection():
    """Получение подключения к базе данных"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('NEW_DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except psycopg2.Error as e:
        print(f"❌ Ошибка подключения: {e}")
        return None


# ==================== CREATE ====================

def create_user(name, email):
    """
    Создание нового пользователя

    :param name: Имя пользователя
    :param email: Email (должен быть уникальным)
    :return: ID созданного пользователя или None
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (name, email)
            VALUES (%s, %s)
            RETURNING id
        """, (name, email))

        user_id = cursor.fetchone()[0]
        conn.commit()
        print(f"✓ Пользователь '{name}' создан с ID: {user_id}")

        cursor.close()
        conn.close()
        return user_id

    except psycopg2.IntegrityError as e:
        print(f"❌ Ошибка: нарушена уникальность (возможно, email занят)")
        conn.rollback()
        cursor.close()
        conn.close()
        return None
    except psycopg2.Error as e:
        print(f"❌ Ошибка создания пользователя: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return None


# ==================== READ ====================

def get_all_users():
    """
    Получение всех пользователей

    :return: Список словарей с данными пользователей
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, email, created_at
            FROM users
            ORDER BY id
        """)

        users = cursor.fetchall()

        cursor.close()
        conn.close()
        return users

    except psycopg2.Error as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        conn.close()
        return []


def get_user_by_id(user_id):
    """
    Получение пользователя по ID

    :param user_id: ID пользователя
    :return: Словарь с данными или None
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, email, created_at
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()

        cursor.close()
        conn.close()
        return user

    except psycopg2.Error as e:
        print(f"❌ Ошибка получения пользователя: {e}")
        conn.close()
        return None


def get_user_by_email(email):
    """
    Получение пользователя по email

    :param email: Email пользователя
    :return: Словарь с данными или None
    """
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, email, created_at
            FROM users
            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        cursor.close()
        conn.close()
        return user

    except psycopg2.Error as e:
        print(f"❌ Ошибка получения пользователя: {e}")
        conn.close()
        return None


# ==================== UPDATE ====================

def update_user(user_id, name=None, email=None):
    """
    Обновление данных пользователя

    :param user_id: ID пользователя
    :param name: Новое имя (опционально)
    :param email: Новый email (опционально)
    :return: True если успешно, иначе False
    """
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Динамическое формирование запроса
        updates = []
        values = []

        if name:
            updates.append("name = %s")
            values.append(name)
        if email:
            updates.append("email = %s")
            values.append(email)

        if not updates:
            print("⚠️ Нет данных для обновления")
            cursor.close()
            conn.close()
            return False

        values.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"

        cursor.execute(query, values)

        if cursor.rowcount == 0:
            print("⚠️ Пользователь не найден")
            cursor.close()
            conn.close()
            return False

        conn.commit()
        print(f"✓ Пользователь с ID {user_id} обновлён")

        cursor.close()
        conn.close()
        return True

    except psycopg2.IntegrityError as e:
        print(f"❌ Ошибка: нарушена уникальность (возможно, email занят)")
        conn.rollback()
        cursor.close()
        conn.close()
        return False
    except psycopg2.Error as e:
        print(f"❌ Ошибка обновления пользователя: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


# ==================== DELETE ====================

def delete_user(user_id):
    """
    Удаление пользователя по ID

    :param user_id: ID пользователя
    :return: True если успешно, иначе False
    """
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM users
            WHERE id = %s
        """, (user_id,))

        if cursor.rowcount == 0:
            print("⚠️ Пользователь не найден")
            cursor.close()
            conn.close()
            return False

        conn.commit()
        print(f"✓ Пользователь с ID {user_id} удалён")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка удаления пользователя: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


# ==================== UTILS ====================

def count_users():
    """
    Подсчёт количества пользователей

    :return: Количество записей в таблице
    """
    conn = get_connection()
    if not conn:
        return 0

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()
        return count

    except psycopg2.Error as e:
        print(f"❌ Ошибка подсчёта: {e}")
        conn.close()
        return 0


def clear_all_users():
    """
    Очистка таблицы пользователей (ОСТОРОЖНО!)

    :return: True если успешно
    """
    conn = get_connection()
    if not conn:
        return False

    confirm = input("⚠️ Вы уверены, что хотите удалить ВСЕХ пользователей? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Операция отменена")
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE users RESTART IDENTITY")
        conn.commit()
        print("✓ Таблица users очищена")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка очистки таблицы: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


# ==================== DEMO ====================

def run_demo():
    """Демонстрация работы с базой данных"""
    print("🚀 Демонстрация работы с базой данных\n")

    # 1. Создаём пользователей
    print("📝 Создание пользователей:")
    create_user("Иван Иванов", "ivan@example.com")
    create_user("Петр Петров", "petr@example.com")
    create_user("Анна Сидорова", "anna@example.com")

    # 2. Получаем всех пользователей
    print("\n📋 Все пользователи:")
    users = get_all_users()
    for user in users:
        print(f"  ID: {user['id']}, Имя: {user['name']}, Email: {user['email']}")

    # 3. Получаем пользователя по ID
    print("\n🔍 Поиск пользователя по ID=1:")
    user = get_user_by_id(1)
    if user:
        print(f"  Найден: {user['name']} ({user['email']})")

    # 4. Обновляем пользователя
    print("\n✏️ Обновление пользователя с ID=1:")
    update_user(1, name="Иван Иванович Иванов")

    # 5. Подсчитываем количество
    print("\n📊 Количество пользователей:")
    print(f"  Всего: {count_users()}")

    # 6. Удаляем пользователя
    print("\n🗑️ Удаление пользователя с ID=2:")
    delete_user(2)

    # 7. Показываем итоговый список
    print("\n📋 Пользователи после изменений:")
    users = get_all_users()
    for user in users:
        print(f"  ID: {user['id']}, Имя: {user['name']}, Email: {user['email']}")

    print("\n✓ Демонстрация завершена")


if __name__ == "__main__":
    run_demo()