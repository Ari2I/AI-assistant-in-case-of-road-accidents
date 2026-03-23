import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import os

load_dotenv()


def get_connection(database=None):
    """Получение подключения к базе данных"""
    db_name = database if database else os.getenv('NEW_DB_NAME')

    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=db_name,
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except psycopg2.Error as e:
        print(f"❌ Ошибка подключения: {e}")
        return None


def add_column(table_name, column_name, column_type, constraints=None):
    """Добавление новой колонки в таблицу"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Проверка существования колонки
        cursor.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))

        if cursor.fetchone():
            print(f"⚠️ Колонка '{column_name}' уже существует в таблице '{table_name}'")
            cursor.close()
            conn.close()
            return False

        # Формирование запроса
        query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if constraints:
            query += f" {constraints}"

        cursor.execute(query)
        conn.commit()
        print(f"✓ Колонка '{column_name}' добавлена в таблицу '{table_name}'")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка добавления колонки: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def drop_column(table_name, column_name):
    """Удаление колонки из таблицы"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Проверка существования колонки
        cursor.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        """, (table_name, column_name))

        if not cursor.fetchone():
            print(f"⚠️ Колонка '{column_name}' не существует в таблице '{table_name}'")
            cursor.close()
            conn.close()
            return False

        query = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        cursor.execute(query)
        conn.commit()
        print(f"✓ Колонка '{column_name}' удалена из таблицы '{table_name}'")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка удаления колонки: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def edit_column(table_name, column_name, new_type, new_constraints=None):
    """Изменение типа или ограничений колонки"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        query = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {new_type}"
        if new_constraints:
            query += f", ALTER COLUMN {column_name} SET {new_constraints}"

        cursor.execute(query)
        conn.commit()
        print(f"✓ Колонка '{column_name}' изменена в таблице '{table_name}'")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка изменения колонки: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def create_table(table_name, columns):
    """
    Создание новой таблицы

    :param table_name: Имя таблицы
    :param columns: Список кортежей [(имя, тип, ограничения), ...]
    """
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = %s
        """, (table_name,))

        if cursor.fetchone():
            print(f"⚠️ Таблица '{table_name}' уже существует")
            cursor.close()
            conn.close()
            return False

        # Формирование запроса
        columns_def = ", ".join([f"{col[0]} {col[1]} {' '.join(col[2:]) if len(col) > 2 else ''}"
                                 for col in columns])
        query = f"CREATE TABLE {table_name} ({columns_def})"

        cursor.execute(query)
        conn.commit()
        print(f"✓ Таблица '{table_name}' создана")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка создания таблицы: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def drop_table(table_name):
    """Удаление таблицы"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # Проверка существования таблицы
        cursor.execute("""
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = %s
        """, (table_name,))

        if not cursor.fetchone():
            print(f"⚠️ Таблица '{table_name}' не существует")
            cursor.close()
            conn.close()
            return False

        query = f"DROP TABLE {table_name} CASCADE"
        cursor.execute(query)
        conn.commit()
        print(f"✓ Таблица '{table_name}' удалена")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка удаления таблицы: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def add_index(table_name, index_name, column_name, unique=False):
    """Добавление индекса на колонку"""
    conn = get_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        unique_str = "UNIQUE " if unique else ""
        query = f"CREATE {unique_str}INDEX {index_name} ON {table_name} ({column_name})"

        cursor.execute(query)
        conn.commit()
        print(f"✓ Индекс '{index_name}' создан на колонке '{column_name}'")

        cursor.close()
        conn.close()
        return True

    except psycopg2.Error as e:
        print(f"❌ Ошибка создания индекса: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False


def run_migration():
    """
    Пример использования миграций
    Раскомментируйте нужные функции для применения изменений
    """
    print("🚀 Запуск миграции базы данных...\n")

    # Пример 1: Добавить колонку phone в таблицу users
    # add_column('users', 'phone', 'VARCHAR(20)', 'DEFAULT NULL')

    # Пример 2: Добавить колонку is_active
    # add_column('users', 'is_active', 'BOOLEAN', 'DEFAULT TRUE')

    # Пример 3: Изменить тип колонки
    # modify_column('users', 'email', 'VARCHAR(255)')

    # Пример 4: Создать новую таблицу
    # create_table('posts', [
    #     ('id', 'SERIAL', 'PRIMARY KEY'),
    #     ('title', 'VARCHAR(200)', 'NOT NULL'),
    #     ('content', 'TEXT'),
    #     ('user_id', 'INTEGER', 'REFERENCES users(id)'),
    #     ('created_at', 'TIMESTAMP', 'DEFAULT CURRENT_TIMESTAMP')
    # ])

    # Пример 5: Добавить индекс
    # add_index('users', 'idx_users_email', 'email', unique=True)

    # Пример 6: Удалить колонку (ОСТОРОЖНО!)
    # drop_column('users', 'old_column')

    # Пример 7: Удалить таблицу (ОСТОРОЖНО!)
    # drop_table('old_table')

    print("\n✓ Миграция завершена")


if __name__ == "__main__":
    run_migration()
    print("""Для осуществления миграции и изменений базы данных нужно раскомментировать функции или добавить
существующие""")