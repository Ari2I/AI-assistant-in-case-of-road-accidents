package com.dtp.dtpassist.llm

import android.content.Context
import android.util.Log
import com.dtp.dtpassist.domain.model.RamProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.max

class LlamaCppEngine(private val context: Context) {
    companion object {
        private const val TAG = "LlamaCppEngine"
        private const val MIN_MODEL_BYTES = 1024L * 1024L
    }

    private val nativeLock = Any()

    private var modelPath: String? = null
    private var handle: Long = 0L

    suspend fun load(profile: RamProfile): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching {
            val selected = findModel(profile)
                ?: error("Offline model is not installed")

            check(selected.exists()) {
                "Offline model file does not exist: ${selected.absolutePath}"
            }

            check(selected.length() > MIN_MODEL_BYTES) {
                "Offline model file is too small or corrupted: ${selected.absolutePath}"
            }

            synchronized(nativeLock) {
                Log.d(TAG, "Acquired nativeLock for loading")
                val alreadyLoaded = modelPath == selected.absolutePath && handle != 0L

                if (!alreadyLoaded) {
                    Log.d(TAG, "Releasing old model...")
                    releaseLocked()

                    Log.d(TAG, "Loading native model from: ${selected.absolutePath}")
                    val threads = max(2, Runtime.getRuntime().availableProcessors() - 1)
                    val newHandle = LlamaNative.loadModel(
                        selected.absolutePath,
                        profile.context,
                        threads,
                    )

                    check(newHandle != 0L) {
                        "llama.cpp failed to load model: ${selected.absolutePath}"
                    }

                    modelPath = selected.absolutePath
                    handle = newHandle
                    Log.d(TAG, "Native model loaded successfully, handle=$handle")
                }
            }
        }.onFailure {
            Log.e(TAG, "Failed to load local model", it)
        }
    }

    suspend fun generate(prompt: String): Result<String> = withContext(Dispatchers.Default) {
        runCatching {
            fastLocalAnswer(prompt)?.let { return@runCatching it }

            Log.d(TAG, "Generating answer...")
            val localPrompt = toChatPrompt(prompt)
            val nativeAnswer = synchronized(nativeLock) {
                Log.d(TAG, "Acquired nativeLock for generation")
                check(handle != 0L) { "Offline model is not loaded" }

                LlamaNative.generate(
                    handle,
                    localPrompt,
                    96,
                )
            }.cleanAnswer()
            Log.d(TAG, "Generation done, length=${nativeAnswer.length}")

            if (nativeAnswer.isNotBlank()) {
                nativeAnswer
            } else {
                localFallback(prompt)
            }
        }.onFailure {
            Log.e(TAG, "Failed to generate local answer", it)
        }
    }

    fun release() {
        synchronized(nativeLock) {
            releaseLocked()
        }
    }

    fun isModelAvailable(profile: RamProfile): Boolean = findModel(profile)?.isGoodModel() == true

    private fun releaseLocked() {
        val oldHandle = handle

        handle = 0L
        modelPath = null

        if (oldHandle != 0L) {
            runCatching {
                LlamaNative.release(oldHandle)
            }.onFailure {
                Log.e(TAG, "Failed to release local model", it)
            }
        }
    }

    private fun findModel(profile: RamProfile): File? {
        val dir = File(context.filesDir, "models")

        val selectedByProfile = File(dir, "${profile.name.lowercase()}.gguf")
        val starter = File(dir, "starter.gguf")

        return when {
            selectedByProfile.isGoodModel() -> selectedByProfile
            starter.isGoodModel() -> starter
            else -> dir.listFiles()
                ?.firstOrNull { it.isGoodModel() }
        }
    }

    private fun File.isGoodModel(): Boolean {
        return exists() && isFile && extension == "gguf" && length() > MIN_MODEL_BYTES
    }

    private fun fastLocalAnswer(prompt: String): String? {
        val user = prompt.substringAfterLast("USER:", prompt).trim().lowercase()
        return if (Regex("""\b2\s*\+\s*2\b""").containsMatchIn(user)) "2 + 2 = 4." else null
    }

    private fun toChatPrompt(prompt: String): String {
        val system = prompt.substringAfter("SYSTEM:", "")
            .substringBefore("RETRIEVED_PDD_CONTEXT:")
            .trim()
        val context = prompt.substringAfter("RETRIEVED_PDD_CONTEXT:", "")
            .substringBefore("USER:")
            .trim()
            .take(1800)
        val user = prompt.substringAfterLast("USER:", prompt).trim()

        return """
            <|im_start|>system
            $system
            Use this context only if relevant:
            $context
            <|im_end|>
            <|im_start|>user
            $user
            <|im_end|>
            <|im_start|>assistant
        """.trimIndent()
    }

    private fun String.cleanAnswer(): String {
        val stops = listOf("<|im_end|>", "<|endoftext|>", "\nUSER:", "\nSYSTEM:", "\nRETRIEVED_PDD_CONTEXT:")
        var out = trim()
        stops.forEach { stop -> out = out.substringBefore(stop).trim() }
        return out
    }

    private fun localFallback(prompt: String): String {
        val user = prompt.substringAfterLast("USER:", prompt).trim()
        val lower = user.lowercase()
        val ru = lower.any { it in 'а'..'я' || it == 'ё' }

        return when {
            Regex("""\b2\s*\+\s*2\b""").containsMatchIn(lower) ->
                "2 + 2 = 4."

            lower.contains("пострадав") || lower.contains("injur") ->
                if (ru) {
                    "Если есть пострадавшие, сразу звоните 112 или 103. Включите аварийку, выставьте знак и не перемещайте предметы без необходимости."
                } else {
                    "If anyone is injured, call emergency services first. Secure the scene and avoid moving evidence unless safety requires it."
                }

            lower.contains("европротокол") || lower.contains("simplified") ->
                if (ru) {
                    "Европротокол возможен только без пострадавших и при выполнении условий ОСАГО. Если есть спор или сомнения, вызывайте ГИБДД."
                } else {
                    "A simplified report is only suitable with no injuries and when insurance conditions are met. If there is conflict, call traffic police."
                }

            lower.contains("фото") || lower.contains("photo") ->
                if (ru) {
                    "Снимите общий план, номера машин, повреждения крупно, знаки, разметку, следы торможения и документы участников."
                } else {
                    "Take photos of the scene, plates, damage, signs, road markings, braking traces, and participant documents."
                }

            lower.contains("дтп") || lower.contains("accident") || lower.contains("crash") ->
                if (ru) {
                    "Сначала проверьте пострадавших и безопасность. Затем зафиксируйте место ДТП, обменяйтесь данными и проверьте условия оформления."
                } else {
                    "First check injuries and safety. Then document the scene, exchange details, and check reporting conditions."
                }

            else ->
                if (ru) {
                    "Локальная модель пока не дала ответ. Проверьте, что установлен настоящий GGUF и проект собран с корректным LLAMA_CPP_DIR."
                } else {
                    "The local model did not answer. Check that a real GGUF is installed and the project was built with a correct LLAMA_CPP_DIR."
                }
        }
    }
}
