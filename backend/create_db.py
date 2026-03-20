import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import os

load_dotenv()

def create_database():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    new_db_name = os.getenv('NEW_DB_NAME')

    cursor.execute("""
        SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s
    """, (new_db_name,))

    if not cursor.fetchone():
        cursor.execute(f'CREATE DATABASE {new_db_name}')
        print(f"✓ База данных '{new_db_name}' создана")
    else:
        print(f"✓ База данных '{new_db_name}' уже существует")

    cursor.close()
    conn.close()


def create_tables():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('NEW_DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    print("✓ Таблица 'users' создана")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_database()
    create_tables()