import os
from django.conf import settings
from dotenv import load_dotenv

# LangChain Imports (из main_AI.py)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from gigachat import GigaChat

# Загружаем переменные окружения
load_dotenv()
GIGA_AUTH = os.getenv("GIGACHAT_CREDENTIALS")

# Пути (адаптированы под Django структуру)
# В main_AI.py: DATA_PATH = "Data_md" -> В Django: docs/knowledge_base
DATA_PATH = os.path.join(settings.BASE_DIR, 'docs', 'knowledge_base')
# В main_AI.py: DB_PATH = "./chroma_db" -> В Django: корень проекта/chroma_db
DB_PATH = os.path.join(settings.BASE_DIR, 'chroma_db')

# Глобальные переменные для кэширования (чтобы не загружать модель каждый раз)
embeddings = None
vectorstore = None


def get_embeddings():
    """Инициализирует модель эмбеддингов один раз."""
    global embeddings
    if embeddings is None:
        print("Загрузка модели эмбеддингов...")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return embeddings


def build_index():
    """
    Создает векторный индекс из markdown файлов.
    Аналог функции build_index() из main_AI.py.
    Запускать один раз при первом запуске или обновлении базы знаний.
    """
    if not os.path.exists(DATA_PATH):
        print(f"Ошибка: Папка {DATA_PATH} не найдена!")
        return None

    loader = DirectoryLoader(DATA_PATH, glob="*.md", loader_cls=UnstructuredMarkdownLoader)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(documents)

    store = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        persist_directory=DB_PATH
    )
    print(f"База готова! Фрагментов: {len(chunks)}")
    return store


def get_vectorstore():
    """Возвращает подключение к базе векторов."""
    global vectorstore
    if vectorstore is None:
        # Проверяем, существует ли база на диске
        if os.path.exists(DB_PATH):
            vectorstore = Chroma(
                persist_directory=DB_PATH,
                embedding_function=get_embeddings()
            )
        else:
            # Если базы нет, создаем её
            vectorstore = build_index()
    return vectorstore


def ask_dtp_bot(query, history=None):
    """
    Основная логика бота из main_AI.py.
    history: список кортежей [(вопрос, ответ), ...]
    """
    if history is None:
        history = []

    db = get_vectorstore()
    if db is None:
        return "Ошибка: База знаний не загружена.", history

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:
        # 1. Фильтр темы (из main_AI.py)
        check_topic = giga.chat(
            f"Вопрос: '{query}'. Этот вопрос касается ДТП, ПДД или автоправа? Ответь только ДА или НЕТ."
        )
        content = check_topic.choices[0].message.content.upper()

        if "НЕТ" in content:
            return "Я — узкопрофильный ассистент по ДТП и не могу ответить на этот вопрос.", history

        # 2. Поиск контекста в векторной базе
        docs = db.similarity_search(query, k=3)
        context = "\n\n".join(
            [f"[Источник: {d.metadata.get('source', 'неизвестен')}]:\n{d.page_content}" for d in docs]
        )

        # 3. Формирование сообщений (System Prompt + История)
        messages = [
            {"role": "system",
             "content": f"""Ты эксперт по ДТП. Тебе необходимо помочь человеку, попавшему в дтп, 
             определиться с планом действий, а так же давать ему рекомендации. 
             Учитывай, что твой собеседник может быть абсолютно неопытным и не знать о существовании Европротокола, 
             отвечай ему кратко и понятно на основе КОНТЕКСТА: {context}."""}
        ]

        # Добавляем историю переписки
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
        return answer, history