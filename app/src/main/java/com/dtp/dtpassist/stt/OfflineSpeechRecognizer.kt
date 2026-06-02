package com.dtp.dtpassist.stt

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import com.dtp.dtpassist.domain.model.AppLanguage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale

class OfflineSpeechRecognizer(private val context: Context) {
    private val _state = MutableStateFlow("idle")
    val state: StateFlow<String> = _state
    private var recognizer: SpeechRecognizer? = null

    fun start(language: AppLanguage, onResult: (String) -> Unit, onError: (String) -> Unit) {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onError("STT недоступен на устройстве")
            return
        }
        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) { _state.value = "listening" }
                override fun onBeginningOfSpeech() { _state.value = "speech" }
                override fun onRmsChanged(rmsdB: Float) = Unit
                override fun onBufferReceived(buffer: ByteArray?) = Unit
                override fun onEndOfSpeech() { _state.value = "processing" }
                override fun onPartialResults(partialResults: Bundle?) = Unit
                override fun onEvent(eventType: Int, params: Bundle?) = Unit
                override fun onError(error: Int) { _state.value = "idle"; onError("STT ошибка: $error") }
                override fun onResults(results: Bundle?) {
                    _state.value = "idle"
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                    if (text.isBlank()) onError("Речь не распознана") else onResult(text)
                }
            })
        }
        val locale = if (language == AppLanguage.RU) Locale("ru", "RU") else Locale.US
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, locale.toLanguageTag())
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 900L)
        }
        try {
            recognizer?.startListening(intent)
        } catch (_: SecurityException) {
            _state.value = "idle"
            onError("Нет доступа к микрофону")
        }
    }

    fun stop() { recognizer?.stopListening(); _state.value = "idle" }
    fun release() { recognizer?.destroy(); recognizer = null }
}
