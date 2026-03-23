import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from gigachat import GigaChat

# Загружаем переменные из .env
load_dotenv()
GIGA_AUTH = os.getenv("GIGA_AUTH")
DATA_PATH = "Data_md"
DB_PATH = "./chroma_db"

# Инициализируем эмбеддинги один раз при запуске
print("Загрузка модели эмбеддингов...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def build_index():
    if not os.path.exists(DATA_PATH):
        print(f"Ошибка: Папка {DATA_PATH} не найдена!")
        return None

    loader = DirectoryLoader(DATA_PATH, glob="*.md", loader_cls=UnstructuredMarkdownLoader)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(documents)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    print(f"База готова! Фрагментов: {len(chunks)}")
    return vectorstore


def ask_dtp_bot(query, history=None):
    if history is None:
        history = []

    # Подключаем существующую базу
    db = Chroma(persist_directory=DB_PATH, embedding_function=embeddings)

    with GigaChat(credentials=GIGA_AUTH, verify_ssl_certs=False) as giga:
        # 1. Фильтр темы
        check_topic = giga.chat(
            f"Вопрос: '{query}'. Этот вопрос касается ДТП, ПДД или автоправа? Ответь только ДА или НЕТ.")
        content = check_topic.choices[0].message.content.upper()

        if "НЕТ" in content:
            return "Я — узкопрофильный ассистент по ДТП и не могу ответить на этот вопрос.", history

        # 2. Поиск контекста
        docs = db.similarity_search(query, k=3)
        context = "\n\n".join(
            [f"[Источник: {d.metadata.get('source', 'неизвестен')}]:\n{d.page_content}" for d in docs])

        # 3. Формирование сообщений
        messages = [
            {"role": "system",
             "content": f"""Ты эксперт по ДТП. Тебе необходимо помочь человеку, попавшему в дтп, 
             определиться с планом действий, а так же давать ему рекомендации. 
             Учитывай, что твой собеседник может быть абсолютно неопытным и не знать о существовании Европротокола, 
             отвечай ему кратко и понятно на основе КОНТЕКСТА: {context}."""}
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
        return answer, history


if __name__ == "__main__":
    # Создаем индекс, если папки с БД еще нет
    if not os.path.exists(DB_PATH):
        build_index()

    chat_history = []
    print("Бот готов к работе. Наберите 'выход' для завершения.") #Закомментировать если не нужно писать эту строку

    while True:
        user_input = input("Вы: ")
        if user_input.lower() in ['выход', 'stop', 'exit']:
            break

        ans, chat_history = ask_dtp_bot(user_input, chat_history)
        print(f"\nБот: {ans}\n")
