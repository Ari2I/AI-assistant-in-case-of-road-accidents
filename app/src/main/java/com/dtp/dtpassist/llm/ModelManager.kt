package com.dtp.dtpassist.llm

import android.content.Context
import com.dtp.dtpassist.domain.model.DownloadState
import com.dtp.dtpassist.domain.model.ModelOption
import com.dtp.dtpassist.domain.model.RamProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class ModelManager(private val context: Context) {
    companion object {
        private const val MIN_MODEL_BYTES = 1024L * 1024L
    }

    private val _download = MutableStateFlow(DownloadState())
    val download: StateFlow<DownloadState> = _download

    val options = listOf(
        ModelOption(
            id = "tiny",
            title = "Qwen2.5 0.5B Instruct Q4_K_M",
            profile = RamProfile.LIGHTWEIGHT,
            url = "https://huggingface.co/bartowski/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/Qwen2.5-0.5B-Instruct-Q4_K_M.gguf",
            sha256 = "PUT_SHA256",
            fileName = "lightweight.gguf",
        ),
        ModelOption(
            id = "balanced",
            title = "Qwen2.5 1.5B Instruct Q4_K_M",
            profile = RamProfile.BALANCED,
            url = "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
            sha256 = "PUT_SHA256",
            fileName = "balanced.gguf",
        ),
        ModelOption(
            id = "high",
            title = "Qwen2.5 3B Instruct Q4_K_M",
            profile = RamProfile.HIGH_QUALITY,
            url = "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf",
            sha256 = "PUT_SHA256",
            fileName = "high_quality.gguf",
        ),
    )

    fun modelExists(profile: RamProfile): Boolean {
        return modelFile(profile).isValidModel()
    }

    fun anyModelExists(): Boolean {
        return File(context.filesDir, "models")
            .listFiles()
            ?.any { it.isValidModel() } == true
    }

    fun delete(profile: RamProfile): Boolean {
        val file = modelFile(profile)
        val tmp = File(file.parentFile, "${file.name}.download")

        val fileDeleted = !file.exists() || file.delete()
        val tmpDeleted = !tmp.exists() || tmp.delete()

        return fileDeleted && tmpDeleted
    }

    suspend fun download(option: ModelOption): Result<File> = withContext(Dispatchers.IO) {
        val dir = File(context.filesDir, "models").apply { mkdirs() }
        val out = modelFile(option.profile)
        val tmp = File(dir, "${out.name}.download")

        runCatching {
            if (out.isValidModel()) {
                _download.value = DownloadState(false, 1f, "Модель уже готова")
                return@runCatching out
            }

            tmp.delete()

            _download.value = DownloadState(
                isDownloading = true,
                progress = 0f,
                message = "Загрузка модели",
            )

            val connection = (URL(option.url).openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 20_000
                readTimeout = 60_000
                instanceFollowRedirects = true
                useCaches = false
                setRequestProperty("User-Agent", "DtpAssist/1.0")
            }

            try {
                val code = connection.responseCode

                if (code !in 200..299) {
                    val errorText = connection.errorStream
                        ?.bufferedReader(Charsets.UTF_8)
                        ?.use { it.readText() }
                        .orEmpty()

                    error("Не удалось скачать модель: HTTP $code ${errorText.take(300)}")
                }

                val totalBytes = connection.contentLengthLong

                connection.inputStream.use { input ->
                    tmp.outputStream().use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        var total = 0L

                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break

                            output.write(buffer, 0, read)
                            total += read

                            val progress = if (totalBytes > 0L) {
                                (total.toFloat() / totalBytes.toFloat()).coerceIn(0f, 1f)
                            } else {
                                -1f
                            }

                            val downloadedMb = total / 1024L / 1024L
                            val message = if (totalBytes > 0L) {
                                val totalMb = totalBytes / 1024L / 1024L
                                "Скачано $downloadedMb / $totalMb МБ"
                            } else {
                                "Скачано $downloadedMb МБ"
                            }

                            _download.value = DownloadState(
                                isDownloading = true,
                                progress = progress,
                                message = message,
                            )
                        }
                    }
                }
            } finally {
                connection.disconnect()
            }

            check(tmp.length() > MIN_MODEL_BYTES) {
                "Скачанный файл слишком маленький. Возможно, вместо модели скачалась HTML-страница ошибки."
            }

            if (option.sha256 != "PUT_SHA256") {
                val actualSha = sha256(tmp)
                check(actualSha.equals(option.sha256, ignoreCase = true)) {
                    tmp.delete()
                    "Повреждён файл модели"
                }
            }

            if (out.exists()) {
                out.delete()
            }

            check(tmp.renameTo(out)) {
                "Не удалось сохранить файл модели"
            }

            _download.value = DownloadState(
                isDownloading = false,
                progress = 1f,
                message = "Модель готова",
            )

            out
        }.onFailure { error ->
            tmp.delete()

            _download.value = DownloadState(
                isDownloading = false,
                progress = 0f,
                message = error.message ?: "Ошибка загрузки",
            )
        }
    }

    private fun modelFile(profile: RamProfile): File {
        return File(context.filesDir, "models/${profile.name.lowercase()}.gguf")
    }

    private fun File.isValidModel(): Boolean {
        return exists() && isFile && extension == "gguf" && length() > MIN_MODEL_BYTES
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")

        file.inputStream().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)

            while (true) {
                val read = input.read(buffer)
                if (read < 0) break

                digest.update(buffer, 0, read)
            }
        }

        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}