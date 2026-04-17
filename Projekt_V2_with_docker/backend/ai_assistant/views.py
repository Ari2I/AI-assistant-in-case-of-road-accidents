import os
import json
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from gigachat import GigaChat

# Глобальные переменные для кэширования
_embeddings = None
_vectorstore = None

# Пути
BASE_DIR = Path(__file__).resolve().parent.parent.parent
AI_AGENT_DIR = BASE_DIR / "AI_agent"
DATA_PATH = AI_AGENT_DIR / "Docs_md"
DB_PATH = AI_AGENT_DIR / "chroma_db"


def get_embeddings():
    """Получить или создать эмбеддинги"""
    global _embeddings
    if _embeddings is None:
        print("Загрузка модели эмбеддингов...")
        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
    return _embeddings


def get_or_build_vectorstore():
    """Получить или построить векторное хранилище"""
    global _vectorstore, _embeddings
    
    if _vectorstore is not None:
        return _vectorstore
    
    embeddings = get_embeddings()
    
    # Проверяем, существует ли уже база
    if os.path.exists(DB_PATH):
        print("Загрузка существующей базы знаний...")
        _vectorstore = Chroma(persist_directory=str(DB_PATH), embedding_function=embeddings)
        return _vectorstore
    
    # Строим новую базу
    if not os.path.exists(DATA_PATH):
        print(f"Ошибка: Папка {DATA_PATH} не найдена!")
        return None
    
    print("Построение базы знаний...")
    loader = DirectoryLoader(str(DATA_PATH), glob="*.md", loader_cls=UnstructuredMarkdownLoader)
    documents = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = text_splitter.split_documents(documents)
    
    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(DB_PATH)
    )
    print(f"База готова! Фрагментов: {len(chunks)}")
    return _vectorstore


def ask_dtp_assistant(query, history=None):
    """
    Основная функция для получения ответа от ИИ-ассистента
    """
    if history is None:
        history = []
    
    # Получаем GigaChat credentials из .env
    giga_auth = os.getenv("GIGA_AUTH")
    if not giga_auth:
        return "Ошибка: не настроен GigaChat. Проверьте переменную окружения GIGA_AUTH.", history
    
    # Получаем векторное хранилище
    db = get_or_build_vectorstore()
    if db is None:
        return "Ошибка: база знаний не доступна.", history
    
    with GigaChat(credentials=giga_auth, verify_ssl_certs=False) as giga:
        # 1. Фильтр темы
        check_topic = giga.chat(
            f"Вопрос: '{query}'. Этот вопрос касается ДТП, ПДД или автоправа? Ответь только ДА или НЕТ."
        )
        content = check_topic.choices[0].message.content.upper()
        
        if "НЕТ" in content:
            return (
                "Я — узкопрофильный ассистент по ДТП и не могу ответить на этот вопрос. "
                "Пожалуйста, спрашивайте о ДТП, ПДД, европротоколе или страховке.",
                history
            )
        
        # 2. Поиск контекста
        docs = db.similarity_search(query, k=3)
        context = "\n\n".join(
            [f"[Источник: {d.metadata.get('source', 'неизвестен')}]:\n{d.page_content}" for d in docs]
        )
        
        # 3. Формирование сообщений
        messages = [
            {
                "role": "system",
                "content": f"""Ты эксперт по ДТП. Тебе необходимо помочь человеку, попавшему в ДТП,
                определиться с планом действий, а также давать ему рекомендации.
                Учитывай, что твой собеседник может быть абсолютно неопытным и не знать о существовании Европротокола,
                отвечай ему кратко и понятно на основе КОНТЕКСТА: {context}."""
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
        return answer, history


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    """
    API endpoint для чата с ИИ-ассистентом
    Ожидает JSON: {"message": "текст вопроса", "history": [["вопрос", "ответ"], ...]}
    Возвращает JSON: {"response": "ответ ассистента", "history": [...]}
    """
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        history = data.get("history", [])
        
        if not message:
            return JsonResponse({
                "error": "Сообщение не может быть пустым"
            }, status=400)
        
        # Получаем ответ от ассистента
        response_text, updated_history = ask_dtp_assistant(message, history)
        
        return JsonResponse({
            "response": response_text,
            "history": updated_history
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            "error": "Неверный формат JSON"
        }, status=400)
    except Exception as e:
        print(f"Ошибка в chat_api: {e}")
        return JsonResponse({
            "error": "Внутренняя ошибка сервера"
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Проверка доступности API
    """
    return JsonResponse({
        "status": "ok",
        "message": "AI Assistant API is running"
    })
