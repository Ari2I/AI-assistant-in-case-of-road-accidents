# Подключение реальной GGUF-модели через llama.cpp JNI

Сейчас проект уже подготовлен. Без `llama.cpp` он собирается со stub и fallback-ответами. Чтобы включить настоящую локальную модель, нужно только скачать `llama.cpp`, указать путь и положить GGUF.

## 1. Что установить

В Android Studio установите:

- Android NDK
- CMake
- LLDB

Проверка: Android Studio -> Settings -> Android SDK -> SDK Tools.

## 2. Скачать llama.cpp

Например:

```powershell
cd C:\Users\vovav\OneDrive\Рабочий стол\and2
git clone https://github.com/ggml-org/llama.cpp
```

Если `git` не установлен, скачайте ZIP с GitHub и распакуйте, например в:

```text
C:\Users\vovav\OneDrive\Рабочий стол\and2\llama.cpp
```

## 3. Указать путь к llama.cpp

В корневом `gradle.properties` добавьте строку:

```properties
LLAMA_CPP_DIR=C:/Users/vovav/OneDrive/Рабочий стол/and2/llama.cpp
```

Используйте прямые слэши `/`, так меньше проблем на Windows.

## 4. Скачать GGUF-модель

Рекомендуемые варианты:

- 2-3 GB RAM: `Qwen2.5-0.5B-Instruct Q4_K_M GGUF`
- 4 GB RAM: `Qwen2.5-1.5B-Instruct Q4_K_M GGUF`
- 6+ GB RAM: `Qwen2.5-3B-Instruct Q4_K_M GGUF`

Положить модель можно через кнопку `Скачать автономное ИИ`, если в `ModelManager` указан реальный URL и SHA-256.

Или вручную положить файл на устройство в private storage приложения:

```text
filesDir/models/lightweight.gguf
filesDir/models/balanced.gguf
filesDir/models/high_quality.gguf
```

Самый простой путь для разработки: временно добавить модель в assets:

```text
app/src/main/assets/models/starter.gguf
```

Но большие модели лучше не класть в APK.

## 5. Где указать URL и SHA модели

Файл:

```text
app/src/main/java/com/dtp/dtpassist/llm/ModelManager.kt
```

Замените:

```kotlin
"https://example.com/balanced.gguf"
"PUT_SHA256"
```

на реальный URL и SHA-256.

## 6. Как собрать

```powershell
java -jar .\gradle\wrapper\gradle-wrapper.jar :app:assembleDebug
```

Если `LLAMA_CPP_DIR` задан правильно, в логе CMake будет:

```text
DtpAssist: building with llama.cpp from ...
```

Если путь не задан:

```text
DtpAssist: LLAMA_CPP_DIR is empty. Building JNI stub.
```

## 7. Как понять, что работает реальная модель

1. В настройках приложения должно быть `Автономное ИИ: установлено`.
2. Включите `Форсировать offline`.
3. Задайте вопрос не из fallback, например:

```text
Объясни простыми словами, когда нельзя оформлять европротокол.
```

Если ответы стали разными и содержательными, работает GGUF. Если ответ шаблонный про fallback, значит `llama.cpp` не подключился или модель не загрузилась.

## 8. Где код JNI

```text
app/src/main/cpp/CMakeLists.txt
app/src/main/cpp/llama_jni.cpp
app/src/main/java/com/dtp/dtpassist/llm/LlamaNative.kt
app/src/main/java/com/dtp/dtpassist/llm/LlamaCppEngine.kt
```

## 9. Возможные ошибки

- `llama.h not found`: неправильный `LLAMA_CPP_DIR`.
- CMake не найден: установить CMake в Android Studio SDK Tools.
- NDK не найден: установить Android NDK.
- Модель не загружается: файл не GGUF, повреждён, слишком большой для RAM.
- Приложение закрывается по памяти: используйте профиль `lightweight` и модель 0.5B Q4.

## 10. Что уже сделано

- Gradle подключает CMake.
- CMake умеет собираться со stub без `llama.cpp`.
- При наличии `LLAMA_CPP_DIR` CMake подключает `llama.cpp`.
- Kotlin вызывает `LlamaNative`.
- `LlamaCppEngine` сначала пытается real native GGUF, потом fallback.
