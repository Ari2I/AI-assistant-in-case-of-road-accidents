# Offline PDD AI

## 1. Краткое архитектурное описание
Офлайн pipeline: микрофон -> `OfflineSpeechRecognizer` с `EXTRA_PREFER_OFFLINE` -> retrieval из `assets/pdd/pdd_ru_en.json` -> `PromptBuilder` -> `LlamaCppEngine` для GGUF/llama.cpp -> `OfflineTts` -> локальная история Room.

Основной стек: GGUF + llama.cpp JNI, системный on-device STT/TTS, JSON/SQLite база ПДД. Запасной стек: Google AI Edge для on-device LLM, но только с локальными моделями; STT/TTS остаются offline/system или Vosk/Piper при добавлении моделей.

## 2. Структура папок проекта
`app`, `ui`, `llm`, `stt`, `tts`, `pdd_knowledge`, `storage`, `audio`, `domain`, `data`, `di`.

## 3. Список зависимостей
Kotlin, Compose Material3, Coroutines/Flow, Room, DataStore, Navigation Compose. Для production llama.cpp добавить `externalNativeBuild` и `jniLibs/arm64-v8a`.

## 4. Основные Kotlin-классы
`AssistantViewModel`, `AssistantRepository`, `PddKnowledgeRepository`, `PromptBuilder`, `LlamaCppEngine`, `ModelManager`, `OfflineSpeechRecognizer`, `OfflineTts`, `SettingsStore`, `ChatDatabase`.

## 5. Prompt template
См. `llm/PromptBuilder.kt`: system, developer, user, retrieved PDD context, language, RAM profile, safety constraints, response format.

## 6. Пример локальной базы ПДД
См. `assets/pdd/pdd_ru_en.json`. Новая статья: добавить объект с `id`, `lang`, `title`, `tags`, `body`; теги влияют на retrieval.

## 7. Пример потока голосового запроса
Пользователь нажимает микрофон -> offline STT возвращает текст -> `ask()` ищет статьи -> строит prompt -> LLM генерирует ответ -> TTS озвучивает -> Room сохраняет историю.

## 8. Инструкция по сборке
Открыть проект в Android Studio, выбрать `app`, собрать Debug. Для стартовой модели положить GGUF в `app/src/main/assets/models/starter.gguf`, при первом запуске скопировать в `filesDir/models/starter.gguf` или добавить copy-step.

## 9. Тесты
`./gradlew testDebugUnitTest` проверяет prompt. Для Android: проверить разрешение микрофона, offline STT pack ru/en, TTS voices, загрузку модели и повреждённый SHA-256.

## 10. Риски и ограничения
Системный STT/TTS офлайн зависит от установленных языковых пакетов устройства. URL моделей сейчас placeholder: заменить на свой CDN/asset server и реальный SHA-256. `LlamaCppEngine` содержит JNI hook и безопасный fallback; для production подключить llama.cpp native binary.

## Замена модели
Добавить GGUF в `ModelManager.options`, выбрать RAM profile, указать URL, имя файла и SHA-256. Рекомендация: 2-3 GB RAM Qwen2.5 0.5B Q4, 4 GB 1.5B Q4, 6+ GB 3B Q4/K_M.

## llama.cpp JNI
Подробная инструкция лежит в `docs/LLAMA_CPP_SETUP.md`. Проект уже содержит `CMakeLists.txt`, `llama_jni.cpp`, `LlamaNative.kt` и подключение в `LlamaCppEngine`. Если `LLAMA_CPP_DIR` не задан, собирается stub; если задан путь к скачанному `llama.cpp`, используется реальный GGUF inference.

## GigaChat
По умолчанию приложение отвечает офлайн даже при наличии интернета. Чтобы включить онлайн-режим, вставьте Basic auth key в `app/build.gradle.kts`:

`buildConfigField("String", "GIGACHAT_AUTH_KEY", "\"ВАШ_КЛЮЧ\"")`

Затем включите переключатель `GigaChat онлайн` в настройках приложения. Если ключ пустой, нет интернета или включён `Форсировать offline`, приложение вернётся к локальному ИИ.

## Что дорабатывать дальше
1. Подключить реальный `llama.cpp` JNI вместо fallback в `LlamaCppEngine`.
2. Заменить placeholder URL/SHA-256 моделей в `ModelManager`.
3. Расширить `pdd_ru_en.json`: больше пунктов ПДД, ОСАГО, европротокол, шаблоны страховой, частые вопросы.
4. Добавить OCR документов и фото ДТП как отдельный модуль после стабилизации базы.
5. Добавить инструмент импорта обновлений базы и моделей отдельно от APK.

## Как тестировать базу знаний
1. Для каждой статьи добавить 5-10 пользовательских формулировок вопроса.
2. Проверить, что `PddKnowledgeRepository.search()` возвращает нужные `id`.
3. Проверить safety cases: `пострадавшие`, `конфликт`, `нет ОСАГО`, `спор`.
4. Тестировать RU и EN отдельно.
5. Включить `Форсировать offline` и убедиться, что ответы не требуют сети.
6. Включить GigaChat и проверить, что retrieved PDD context попадает в prompt и модель не выдумывает правила.
