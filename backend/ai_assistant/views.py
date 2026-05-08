import json
import sys
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


AI_MODULE_DIR = Path(__file__).resolve().parent
if str(AI_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_MODULE_DIR))

from agent.core import run_agent  # noqa: E402
from rag.init_db import load_db, load_feedback_db  # noqa: E402
from .models import ChatMessage


_db = None
_feedback_db = None
_HISTORY_LIMIT = 20


def _get_db():
    global _db
    if _db is None:
        _db = load_db()
    return _db


def _get_feedback_db():
    global _feedback_db
    if _feedback_db is None:
        try:
            _feedback_db = load_feedback_db()
        except Exception as exc:
            print(f"[ai_assistant] feedback db unavailable: {exc}")
            _feedback_db = False
    return None if _feedback_db is False else _feedback_db


def _get_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


def _history_queryset(request):
    if request.user.is_authenticated:
        return ChatMessage.objects.filter(user=request.user)

    return ChatMessage.objects.filter(session_key=_get_session_key(request))


def _load_history(request):
    messages = list(_history_queryset(request).order_by("-created_at")[:_HISTORY_LIMIT])
    messages.reverse()
    return [
        {
            "query": message.query,
            "answer": message.answer,
        }
        for message in messages
    ]


def _save_message(request, query, result):
    ChatMessage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=_get_session_key(request),
        query=query,
        answer=result.get("answer", ""),
        source=result.get("source") or "",
        category=result.get("category") or "",
    )


@csrf_exempt
@require_http_methods(["POST"])
def chat_api(request):
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()

        if not message:
            return JsonResponse({"error": "Сообщение не может быть пустым"}, status=400)

        history = _load_history(request)
        result = run_agent(
            query=message,
            history=history,
            db=_get_db(),
            feedback_db=_get_feedback_db(),
        )

        answer = result.get("answer", "")
        _save_message(request, message, result)
        history.append({"query": message, "answer": answer})

        return JsonResponse(
            {
                "response": answer,
                "history": history,
                "source": result.get("source"),
                "category": result.get("category"),
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"error": "Неверный формат JSON"}, status=400)
    except Exception as exc:
        print(f"[ai_assistant] chat_api error: {exc}")
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def chat_history_api(request):
    try:
        return JsonResponse({"history": _load_history(request)})
    except Exception as exc:
        print(f"[ai_assistant] chat_history_api error: {exc}")
        return JsonResponse({"error": "Внутренняя ошибка сервера"}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    return JsonResponse(
        {
            "status": "ok",
            "message": "AI Assistant API is running",
        }
    )
