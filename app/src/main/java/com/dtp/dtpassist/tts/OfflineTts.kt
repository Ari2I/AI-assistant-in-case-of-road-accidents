package com.dtp.dtpassist.tts

import android.content.Context
import android.speech.tts.TextToSpeech
import com.dtp.dtpassist.domain.model.AppLanguage
import java.util.Locale

class OfflineTts(context: Context) : TextToSpeech.OnInitListener {
    private var ready = false
    private val tts = TextToSpeech(context.applicationContext, this)

    override fun onInit(status: Int) { ready = status == TextToSpeech.SUCCESS }

    fun speak(text: String, language: AppLanguage, rate: Float): Result<Unit> = runCatching {
        check(ready) { "TTS недоступен" }
        tts.language = if (language == AppLanguage.RU) Locale("ru", "RU") else Locale.US
        tts.setSpeechRate(rate)
        val r = tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "answer-${System.currentTimeMillis()}")
        check(r == TextToSpeech.SUCCESS) { "TTS не запустился" }
    }

    fun stop() = tts.stop()
    fun release() = tts.shutdown()
}
