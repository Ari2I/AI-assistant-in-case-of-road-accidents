package com.dtp.dtpassist.ui.chat

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.dtp.dtpassist.di.AppContainer
import com.dtp.dtpassist.domain.model.AiAssistantStep
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.ChatMessage
import com.dtp.dtpassist.domain.model.ChatThread
import com.dtp.dtpassist.domain.model.RamProfile
import com.dtp.dtpassist.storage.AppSettings
import com.dtp.dtpassist.storage.UserProfile
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

data class UiState(
    val input: String = "",
    val messages: List<ChatMessage> = emptyList(),
    val settings: AppSettings = AppSettings(),
    val busy: Boolean = false,
    val mic: String = "idle",
    val error: String? = null,
    val online: Boolean = false,
    val gigaConfigured: Boolean = false,
    val offlineModelInstalled: Boolean = false,
    val location: String = "",
    val profile: UserProfile = UserProfile(),
    val step: AiAssistantStep = AiAssistantStep.STEP1,
    val chats: List<ChatThread> = emptyList(),
    val currentChatId: Long = 0L,
)

class AssistantViewModel(private val c: AppContainer) : ViewModel() {
    private val _state = MutableStateFlow(
        UiState(
            online = c.connectivity.isOnline(),
            gigaConfigured = c.gigaChat.isConfigured(),
            offlineModelInstalled = c.modelManager.anyModelExists(),
        ),
    )

    val state: StateFlow<UiState> = _state
    val download = c.modelManager.download.stateIn(
        viewModelScope,
        SharingStarted.Eagerly,
        com.dtp.dtpassist.domain.model.DownloadState(),
    )

    init {
        viewModelScope.launch { c.assistant.ensureActiveChat() }
        viewModelScope.launch { c.assistant.history.collect { _state.value = _state.value.copy(messages = it) } }
        viewModelScope.launch { c.assistant.chats.collect { _state.value = _state.value.copy(chats = it) } }
        viewModelScope.launch { c.assistant.currentChatId.collect { _state.value = _state.value.copy(currentChatId = it) } }
        viewModelScope.launch { c.assistant.currentStep.collect { _state.value = _state.value.copy(step = it) } }
        viewModelScope.launch { c.settings.settings.collect { _state.value = _state.value.copy(settings = it) } }
        viewModelScope.launch { c.profile.profile.collect { _state.value = _state.value.copy(profile = it) } }
        viewModelScope.launch { c.stt.state.collect { _state.value = _state.value.copy(mic = it) } }
        viewModelScope.launch { monitorConnectivity() }
    }

    fun input(v: String) {
        _state.value = _state.value.copy(input = v, error = null, online = effectiveOnline())
    }

    fun send() = viewModelScope.launch {
        val text = _state.value.input.trim()
        if (text.isBlank()) return@launch

        Log.d("AssistantVM", "Sending message: $text")
        _state.value = _state.value.copy(input = "", busy = true, error = null, online = effectiveOnline())

        try {
            val settings = _state.value.settings
            val answer = withTimeoutOrNull(30_000L) {
                c.assistant.ask(
                    text = text,
                    settings = settings,
                    profile = settings.profile,
                    useGigaChat = settings.useGigaChat,
                    online = effectiveOnline(),
                )
            } ?: "РџСЂРµРІС‹С€РµРЅРѕ РІСЂРµРјСЏ РѕР¶РёРґР°РЅРёСЏ РѕС‚РІРµС‚Р°. РџСЂРѕРІРµСЂСЊС‚Рµ СЃРѕРµРґРёРЅРµРЅРёРµ РёР»Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰Рµ СЂР°Р·."

            Log.d("AssistantVM", "Received answer: ${answer.take(20)}...")
            if (settings.autoSpeak) {
                c.tts.speak(answer, detectLanguage(answer), settings.speechRate)
            }
        } catch (e: Exception) {
            Log.e("AssistantVM", "Error in send()", e)
            _state.value = _state.value.copy(error = e.message)
        } finally {
            _state.value = _state.value.copy(
                busy = false,
                offlineModelInstalled = c.modelManager.anyModelExists(),
                gigaConfigured = c.gigaChat.isConfigured(_state.value.settings),
            )
        }
    }

    fun startVoice() {
        c.stt.start(
            _state.value.settings.language,
            onResult = {
                input(it)
                send()
            },
            onError = { _state.value = _state.value.copy(error = it) },
        )
    }

    fun stopVoice() = c.stt.stop()

    fun stopSpeaking() = c.tts.stop()

    fun speakLast() {
        val last = _state.value.messages.lastOrNull { !it.isUser }?.text ?: return
        c.tts.speak(last, detectLanguage(last), _state.value.settings.speechRate)
    }

    fun setLanguage(v: AppLanguage) = viewModelScope.launch { c.settings.setLanguage(v) }
    fun setProfile(v: RamProfile) = viewModelScope.launch { c.settings.setProfile(v) }
    fun setAutoSpeak(v: Boolean) = viewModelScope.launch { c.settings.setAutoSpeak(v) }
    fun setSpeechRate(v: Float) = viewModelScope.launch { c.settings.setSpeechRate(v) }
    fun setUseGigaChat(v: Boolean) = viewModelScope.launch { c.settings.setUseGigaChat(v) }

    fun setForceOffline(v: Boolean) = viewModelScope.launch {
        c.settings.setForceOffline(v)
        val online = c.connectivity.isOnline() && !v
        _state.value = _state.value.copy(online = online)
    }

    fun saveProfile(v: UserProfile) = viewModelScope.launch { c.profile.save(v) }

    fun fetchLocation() = viewModelScope.launch {
        val point = c.location.lastPoint()
        _state.value = _state.value.copy(location = point)
        input("РњРѕСЏ РіРµРѕС‚РѕС‡РєР° Р”РўРџ: $point. РџРѕРґСЃРєР°Р¶Рё, С‡С‚Рѕ РґРµР»Р°С‚СЊ РґР°Р»СЊС€Рµ.")
    }

    fun downloadAi() = viewModelScope.launch {
        c.modelManager.download(c.modelManager.options.first { it.profile == _state.value.settings.profile })
        _state.value = _state.value.copy(offlineModelInstalled = c.modelManager.anyModelExists())
    }

    fun deleteAi() = viewModelScope.launch {
        c.modelManager.delete(_state.value.settings.profile)
        _state.value = _state.value.copy(offlineModelInstalled = c.modelManager.anyModelExists())
    }

    fun clearHistory() = viewModelScope.launch {
        c.assistant.clear()
    }

    fun createNewChat() = viewModelScope.launch {
        c.assistant.createNewChat("Чат ${System.currentTimeMillis()}")
    }

    fun switchChat(chatId: Long) = viewModelScope.launch {
        c.assistant.switchChat(chatId)
    }

    fun clearAllChatsHistory() = viewModelScope.launch {
        c.assistant.clearAll()
    }

    private suspend fun monitorConnectivity() {
        while (true) {
            val online = effectiveOnline()
            _state.value = _state.value.copy(
                online = online,
                gigaConfigured = c.gigaChat.isConfigured(_state.value.settings),
                offlineModelInstalled = c.modelManager.anyModelExists(),
            )
            delay(3_000)
        }
    }

    private fun effectiveOnline(): Boolean = c.connectivity.isOnline() && !_state.value.settings.forceOffline

    private fun detectLanguage(text: String): AppLanguage {
        val cyr = text.count { it in 'а'..'я' || it in 'А'..'Я' || it == 'ё' || it == 'Ё' }
        val lat = text.count { it in 'a'..'z' || it in 'A'..'Z' }
        return if (cyr >= lat) AppLanguage.RU else AppLanguage.EN
    }
}

