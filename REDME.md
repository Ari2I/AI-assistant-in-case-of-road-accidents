# DtpAssist: технический REDME (RU)

## 1) Где находится проект

- Корень Android-проекта: `C:\Users\vovav\OneDrive\Рабочий стол\and2\app`
- Модуль приложения: `C:\Users\vovav\OneDrive\Рабочий стол\and2\app\app`
- Основной Kotlin-код: `C:\Users\vovav\OneDrive\Рабочий стол\and2\app\app\src\main\java\com\dtp\dtpassist`

## 2) Кратко о назначении

Приложение помогает в сценариях ДТП и работает с двумя источниками ответов:

- `GigaChat` (онлайн)
- локальная `LLM` через `llama.cpp` + GGUF-модель (оффлайн/локально)

Переключение источника делается в настройках ИИ внутри профиля пользователя.

## 3) Архитектура: что за что отвечает

### 3.1 UI (визуальная часть)

- Главная композиция/навигация:
  - [AccidentAssistantApp.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/app/AccidentAssistantApp.kt)
- Экран чата:
  - [ChatScreen.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/screens/ChatScreen.kt)
- Экран профиля:
  - [ProfileScreen.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/screens/ProfileScreen.kt)
- Доп. экраны:
  - [InstructionsScreen.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/screens/InstructionsScreen.kt)
  - [DocsScreen.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/screens/DocsScreen.kt)
  - [ConstructorScreen.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/screens/ConstructorScreen.kt)

### 3.2 ViewModel (состояние и действия UI)

- [AssistantViewModel.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/chat/AssistantViewModel.kt)
  - хранит `UiState`
  - отправляет сообщения
  - подтягивает историю чата
  - следит за онлайн-статусом
  - прокидывает настройки ИИ в репозиторий

### 3.3 Бизнес-логика ответа (маршрутизация между LLM и GigaChat)

- [AssistantRepository.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/repository/AssistantRepository.kt)
  - центральная точка `ask(...)`
  - если включен `GigaChat`, идет в `GigaChatClient`
  - если выключен `GigaChat`, идет в `LlamaCppEngine`
  - пишет сообщения в БД
  - определяет шаг сценария ДТП

### 3.4 GigaChat (онлайн модель)

- [GigaChatClient.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/network/GigaChatClient.kt)
  - запросы к OAuth и chat/completions
  - кеш access token
  - поддержка runtime-настроек:
    - `gigaChatAuthKey`
    - `gigaChatAccessToken`
  - fallback на BuildConfig-ключ, если runtime ключ пуст

### 3.5 Локальная модель (LLM на устройстве)

- [LlamaCppEngine.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/LlamaCppEngine.kt)
  - загрузка GGUF
  - генерация ответа
  - проверка доступности модели
- [LlamaNative.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/LlamaNative.kt)
  - JNI-мост к native библиотеке
- [ModelManager.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/ModelManager.kt)
  - скачивание/удаление GGUF
  - прогресс загрузки

### 3.6 Промпт и PDD/RAG-контекст

- [PromptBuilder.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/PromptBuilder.kt)
  - собирает системный промпт + контекст
- [PddKnowledge.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/pdd_knowledge/PddKnowledge.kt)
  - локальный поиск по базе ПДД из assets

### 3.7 Настройки, DI, хранилища, БД

- [SettingsStore.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/storage/SettingsStore.kt)
  - `useGigaChat`, `profile`, `gigaChatAuthKey`, `gigaChatAccessToken`, etc.
- [ProfileStore.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/storage/ProfileStore.kt)
  - профиль пользователя
- [AppContainer.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/di/AppContainer.kt)
  - связывает зависимости
- [ChatDatabase.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/local/ChatDatabase.kt)
  - Room БД истории чатов

## 4) Как работает запрос в чат

1. Пользователь пишет сообщение в `ChatScreen`.
2. `AssistantViewModel.send()` вызывает `AssistantRepository.ask(...)`.
3. `AssistantRepository` проверяет настройки:
   - `useGigaChat=true` -> `GigaChatClient`
   - `useGigaChat=false` -> `LlamaCppEngine`
4. Ответ сохраняется в Room и отображается в чате.

## 5) Где именно переключается источник ИИ

- Логика переключателя в UI: [AccidentAssistantApp.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/app/AccidentAssistantApp.kt) (`AiSettingsDialog`)
- Сохранение переключателя: [SettingsStore.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/storage/SettingsStore.kt)
- Применение переключателя при ответе: [AssistantRepository.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/repository/AssistantRepository.kt)

## 6) Где визуал и ресурсы

- Compose UI:
  - `.../ui/app`
  - `.../ui/screens`
  - `.../ui/components`
  - `.../ui/theme`
- Android ресурсы:
  - `C:\Users\vovav\OneDrive\Рабочий стол\and2\app\app\src\main\res`
- PDD JSON:
  - `C:\Users\vovav\OneDrive\Рабочий стол\and2\app\app\src\main\assets\pdd\pdd_ru_en.json`

## 7) Что нужно для продолжения работы в новом чате (минимум)

Переносить в новый чат в первую очередь:

1. [AssistantRepository.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/repository/AssistantRepository.kt)
2. [GigaChatClient.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/network/GigaChatClient.kt)
3. [AssistantViewModel.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/chat/AssistantViewModel.kt)
4. [AccidentAssistantApp.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/ui/app/AccidentAssistantApp.kt)
5. [SettingsStore.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/storage/SettingsStore.kt)
6. [LlamaCppEngine.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/LlamaCppEngine.kt)
7. [ModelManager.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/ModelManager.kt)
8. [PromptBuilder.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/llm/PromptBuilder.kt)
9. [ChatDatabase.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/data/local/ChatDatabase.kt)
10. [PddKnowledge.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/pdd_knowledge/PddKnowledge.kt)
11. [AppContainer.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/di/AppContainer.kt)
12. [AiModels.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/domain/model/AiModels.kt)
13. [AiAssistantStep.kt](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/src/main/java/com/dtp/dtpassist/domain/model/AiAssistantStep.kt)
14. [app/build.gradle.kts](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/app/build.gradle.kts)
15. [gradlew.bat](C:/Users/vovav/OneDrive/Рабочий%20стол/and2/app/gradlew.bat)

## 8) Что обычно НЕ нужно переносить в новый чат

Не обязательно включать в контекст:

- `build/`, `.gradle/`, `.kotlin/`, `.idea/`
- `konstructor/` (отдельный большой блок, не влияет на текущий чат-ИИ поток)
- `third_party/llama.cpp/` (исходники сторонней библиотеки; обычно не редактируем)
- `AI assistant/` (питоновский блок, отдельный от Android-пайплайна чата)
- бинарники/архивы: `app.7z`, apk-артефакты, временные кэши
- docs, не относящиеся к текущей правке

## 9) Команды проверки

- Сборка debug:
  - `java -jar .\gradle\wrapper\gradle-wrapper.jar :app:assembleDebug`

## 10) Важные замечания

- `GigaChat` работает только при валидных credentials в настройках.
- Локальная ветка требует GGUF для выбранного профиля RAM.
- Если в чате важна экономия токенов контекста: грузить только файлы из раздела 7.
