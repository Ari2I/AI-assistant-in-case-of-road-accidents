# ai_assistant/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .services import ask_dtp_bot


@csrf_exempt
@require_http_methods(["POST"])
def chat_view(request):
    """
    API endpoint для чата с AI-ассистентом.
    URL: /api/chat
    Метод: POST
    """
    try:
        # Парсим JSON из тела запроса
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Получаем сообщение пользователя
    message = data.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Message is required'}, status=400)

    # Получаем историю переписки (опционально)
    # Формат: [["вопрос 1", "ответ 1"], ["вопрос 2", "ответ 2"]]
    history_data = data.get('history', [])

    # Конвертируем историю в формат кортежей для services.py
    history = []
    for item in history_data:
        if isinstance(item, list) and len(item) >= 2:
            history.append((item[0], item[1]))

    # Вызываем основную логику AI
    try:
        reply, new_history = ask_dtp_bot(message, history)
    except Exception as e:
        return JsonResponse({'error': f'AI service error: {str(e)}'}, status=500)

    # Конвертируем историю обратно в списки для JSON
    history_response = [[q, a] for q, a in new_history]

    return JsonResponse({
        'reply': reply,
        'history': history_response
    })