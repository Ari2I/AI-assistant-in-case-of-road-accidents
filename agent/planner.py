def plan(giga, query, history_text):
    response = giga.chat(f"""
    Ты определяешь намерение пользователя при ДТП.
    
    История:
    {history_text}
    
    Сообщение:
    {query}
    
    Верни JSON:
    {{
      "intent": "что хочет пользователь",
      "stage": "accident | europrotocol | insurance | dispute | other",
      "answer_type": "steps | explanation | question"
    }}
    """)

    text = response.choices[0].message.content

    import json, re

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        return json.loads(text)
    except:
        return {
            "intent": "unknown",
            "stage": "other",
            "answer_type": "explanation"
        }