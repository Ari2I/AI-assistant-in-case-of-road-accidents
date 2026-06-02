package com.dtp.dtpassist.data.network

import android.util.Log
import com.dtp.dtpassist.BuildConfig
import com.dtp.dtpassist.storage.AppSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.UUID
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

class GigaChatClient {
    companion object {
        private const val TAG = "GigaChatClient"

        private const val AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        private const val CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

        private const val MODEL = "GigaChat"
        private const val SCOPE = "GIGACHAT_API_PERS"
        private const val SYSTEM_GUARDRAIL = "Ты ИИ-ассистент по ДТП и ОСАГО. В первую очередь опирайся на переданный контекст базы ассистента. Если данных недостаточно, так и скажи и задай уточняющий вопрос по теме ДТП/ОСАГО."
    }

    @Volatile
    private var cachedToken: String? = null

    @Volatile
    private var tokenExpiresAtMs: Long = 0L

    @Volatile
    private var cachedAuthKey: String? = null

    init {
        if (BuildConfig.DEBUG) {
            disableSslVerificationForDebugOnly()
        }
    }

    fun isConfigured(settings: AppSettings? = null): Boolean {
        return configuredAuthKey().isNotBlank()
    }

    suspend fun ask(prompt: String, settings: AppSettings? = null): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            askOnce(prompt, settings)
        }.recoverCatching { error ->
            if (error.message?.contains("HTTP 401") == true) {
                invalidateToken()
                askOnce(prompt, settings)
            } else {
                throw error
            }
        }.onFailure {
            Log.e(TAG, "GigaChat request failed", it)
        }
    }

    private fun askOnce(prompt: String, settings: AppSettings?): String {
        val token = resolveAccessToken(settings)

        val body = JSONObject()
            .put("model", MODEL)
            .put(
                "messages",
                JSONArray()
                    .put(
                        JSONObject()
                            .put("role", "system")
                            .put("content", SYSTEM_GUARDRAIL),
                    )
                    .put(
                        JSONObject()
                            .put("role", "user")
                            .put("content", prompt),
                    ),
            )
            .put("temperature", 0.2)
            .put("max_tokens", 220)
            .put("stream", false)
            .toString()

        val response = postJson(
            url = CHAT_URL,
            body = body,
            headers = mapOf(
                "Authorization" to "Bearer $token",
                "Content-Type" to "application/json",
                "Accept" to "application/json",
            ),
        )

        val json = JSONObject(response)
        val choices = json.getJSONArray("choices")
        check(choices.length() > 0) { "GigaChat returned empty choices" }

        return choices
            .getJSONObject(0)
            .getJSONObject("message")
            .getString("content")
    }

    private fun resolveAccessToken(settings: AppSettings?): String {
        val auth = configuredAuthKey()
        check(auth.isNotBlank()) { "GigaChat credentials are empty" }
        return token(auth)
    }

    private fun configuredAuthKey(): String {
        val buildKey = normalizeAuthKey(BuildConfig.GIGACHAT_API_PERS)
        return if (buildKey.isUsableSecret()) buildKey else ""
    }

    private fun normalizeAuthKey(raw: String): String {
        return raw.trim().removePrefix("Basic ").trim()
    }

    private fun token(auth: String): String {
        val now = System.currentTimeMillis()

        if (cachedAuthKey != auth) {
            invalidateToken()
            cachedAuthKey = auth
        }

        cachedToken?.let { cached ->
            if (cached.isNotBlank() && now < tokenExpiresAtMs - 60_000L) {
                return cached
            }
        }

        synchronized(this) {
            val cached = cachedToken
            if (!cached.isNullOrBlank() && now < tokenExpiresAtMs - 60_000L) {
                return cached
            }

            val response = postForm(
                url = AUTH_URL,
                body = "scope=$SCOPE",
                headers = mapOf(
                    "Authorization" to "Basic $auth",
                    "RqUID" to UUID.randomUUID().toString(),
                    "Content-Type" to "application/x-www-form-urlencoded",
                    "Accept" to "application/json",
                ),
            )

            val json = JSONObject(response)
            val accessToken = json.getString("access_token")

            val rawExpiresAt = json.optLong("expires_at", 0L)
            tokenExpiresAtMs = when {
                rawExpiresAt > 10_000_000_000L -> rawExpiresAt
                rawExpiresAt > 0L -> rawExpiresAt * 1000L
                else -> System.currentTimeMillis() + 25L * 60L * 1000L
            }

            cachedToken = accessToken
            return accessToken
        }
    }

    private fun invalidateToken() {
        cachedToken = null
        tokenExpiresAtMs = 0L
    }

    private fun String.isUsableSecret(): Boolean {
        return isNotBlank() &&
            this != "PUT_GIGACHAT_KEY_HERE" &&
            !contains("xxxxx", ignoreCase = true)
    }

    private fun postJson(
        url: String,
        body: String,
        headers: Map<String, String>,
    ): String {
        val connection = (URL(url).openConnection() as HttpsURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8_000
            readTimeout = 20_000
            doOutput = true
            useCaches = false
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
        }

        return execute(connection, body)
    }

    private fun postForm(
        url: String,
        body: String,
        headers: Map<String, String>,
    ): String {
        val connection = (URL(url).openConnection() as HttpsURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8_000
            readTimeout = 12_000
            doOutput = true
            useCaches = false
            headers.forEach { (key, value) -> setRequestProperty(key, value) }
        }

        return execute(connection, body)
    }

    private fun execute(connection: HttpURLConnection, body: String): String {
        try {
            connection.outputStream.use {
                it.write(body.toByteArray(Charsets.UTF_8))
            }

            val code = connection.responseCode
            val response = readBody(connection, code)

            if (code !in 200..299) {
                error("HTTP $code: ${response.take(1000)}")
            }

            return response
        } finally {
            connection.disconnect()
        }
    }

    private fun readBody(connection: HttpURLConnection, code: Int): String {
        val stream = try {
            if (code in 200..299) {
                connection.inputStream
            } else {
                connection.errorStream ?: connection.inputStream
            }
        } catch (e: Exception) {
            connection.errorStream ?: throw e
        }

        return stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
    }

    private fun disableSslVerificationForDebugOnly() {
        try {
            val trustAllCerts = arrayOf<TrustManager>(
                object : X509TrustManager {
                    override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
                    override fun checkClientTrusted(certs: Array<X509Certificate>, authType: String) = Unit
                    override fun checkServerTrusted(certs: Array<X509Certificate>, authType: String) = Unit
                },
            )

            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(null, trustAllCerts, SecureRandom())

            HttpsURLConnection.setDefaultSSLSocketFactory(sslContext.socketFactory)
            HttpsURLConnection.setDefaultHostnameVerifier { _, _ -> true }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to disable SSL verification in debug mode", e)
        }
    }
}
