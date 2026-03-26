import os
import json
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from gigachat import GigaChat

# Загружаем переменные из .env
load_dotenv()
GIGA_AUTH = os.getenv("GIGA_AUTH")

DATA_PATH = "Data_md"
DB_PATH = "./chroma_db"
HISTORY_DIR = "history"

os.makedirs(HISTORY_DIR, exist_ok=True)

# Инициализируем эмбеддинги один раз при запуске
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def build_index():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Папка {DATA_PATH} не найдена")

    loader = DirectoryLoader(
        DATA_PATH,
        glob="*.md",
        loader_cls=UnstructuredMarkdownLoader
    )
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(documents)

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    return db

# =========================
# 💾 ИСТОРИЯ ПО USER_ID
# =========================
def get_history_path(user_id):
    return os.path.join(HISTORY_DIR, f"{user_id}.json")


def load_history(user_id):
    path = get_history_path(user_id)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(user_id, history):
    path = get_history_path(user_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def ask_dtp_bot(query, db, user_id):
    history = load_history(user_id)

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:
        # 1. Фильтр темы
        check_topic = giga.chat(
            f"""Вопрос: '{query}'. Этот вопрос касается ДТП, ПДД или автоправа? Ответь только ДА или НЕТ.""")
        content = check_topic.choices[0].message.content.strip().upper()

        if content != "ДА":
            return "Я — ассистент только по ДТП и ПДД. Задайте вопрос по теме."

        # 2. Поиск контекста
        docs_with_scores = db.similarity_search_with_score(query, k=5)

        filtered_docs = [doc for doc, score in docs_with_scores if score < 0.5]

        if not filtered_docs:
            context = "Нет данных из базы. Ответь на основе общих знаний."
        else:
            context = "\n\n".join([
                f"[Источник: {d.metadata.get('source', 'неизвестен')}]:\n{d.page_content}"
                for d in filtered_docs
            ])

        # 3. Формирование сообщений
        messages = [
            {
                "role": "system",
                "content": f"""
            Ты эксперт по ДТП и ПДД.

            Твоя задача:
            - помочь человеку после ДТП
            - дать чёткий пошаговый план
            - объяснять максимально просто
            - избегать сложных юридических терминов
            - если нет данных — честно сказать

            Отвечай кратко и по делу.

            КОНТЕКСТ:
            {context}
            """
            }
        ]

        # Добавляем историю
        for user_msg, bot_msg in history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": bot_msg})

        messages.append({"role": "user", "content": query})

        # 4. Запрос к модели
        payload = {
            "messages": messages,
            "temperature": 0.1
        }
        response = giga.chat(payload)
        answer = response.choices[0].message.content

        history.append((query, answer))
        save_history(user_id, history)

        return answer

# =========================
# 🚀 ИНИЦИАЛИЗАЦИЯ
# =========================
def init_bot():
    if not os.path.exists(DB_PATH):
        db = build_index()
    else:
        db = Chroma(
            persist_directory=DB_PATH,
            embedding_function=embeddings
        )
    return db

"""Раскомментировать для локального запуска"""
# if __name__ == "__main__":
#     db = init_bot()
#
#     # временный user_id (эмуляция пользователя)
#     user_id = "test_user"
#
#     while True:
#         query = input("Ты: ")
#
#         if query.lower() in ["exit", "quit", "выход"]:
#             break
#
#         answer = ask_dtp_bot(query, db, user_id)
#         print("\nБот:", answer, "\n")
