package com.dtp.dtpassist.data.repository

import com.dtp.dtpassist.data.local.ChatDao
import com.dtp.dtpassist.data.local.ChatEntity
import com.dtp.dtpassist.data.local.ChatThreadEntity
import com.dtp.dtpassist.data.network.GigaChatClient
import com.dtp.dtpassist.domain.model.AiAssistantStep
import com.dtp.dtpassist.domain.model.ChatMessage
import com.dtp.dtpassist.domain.model.ChatThread
import com.dtp.dtpassist.domain.model.RamProfile
import com.dtp.dtpassist.llm.LlamaCppEngine
import com.dtp.dtpassist.llm.PromptBuilder
import com.dtp.dtpassist.pdd_knowledge.AiAssistantRagRepository
import com.dtp.dtpassist.pdd_knowledge.PddKnowledgeRepository
import com.dtp.dtpassist.storage.AppSettings
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

class AssistantRepository(
    private val chatDao: ChatDao,
    private val pdd: PddKnowledgeRepository,
    private val aiAssistantRag: AiAssistantRagRepository,
    private val localEngine: LlamaCppEngine,
    private val promptBuilder: PromptBuilder,
    private val gigaChat: GigaChatClient,
) {
    private data class SessionState(
        val offeredEuro: Boolean = false,
    )

    private val sessionByChatId = mutableMapOf<Long, SessionState>()
    private val _currentChatId = MutableStateFlow(0L)
    val currentChatId: Flow<Long> = _currentChatId
    val chats: Flow<List<ChatThread>> = chatDao.observeChats().map { items ->
        items.map { ChatThread(id = it.id, title = it.title, createdAt = it.createdAt) }
    }
    val history: Flow<List<ChatMessage>> = _currentChatId.flatMapLatest { chatId ->
        chatDao.observe(chatId).map { messages ->
            messages.map { ChatMessage(id = it.id, text = it.text, isUser = it.isUser, createdAt = it.createdAt) }
        }
    }

    val currentStep = MutableStateFlow(AiAssistantStep.STEP1)

    suspend fun ensureActiveChat() {
        if (_currentChatId.value != 0L && chatDao.getChatById(_currentChatId.value) != null) return
        val latest = chatDao.getLatestChat()
        if (latest != null) {
            _currentChatId.value = latest.id
            return
        }
        createNewChat("Новый чат")
    }

    suspend fun createNewChat(title: String = "Новый чат"): Long {
        val now = System.currentTimeMillis()
        val chatId = now
        chatDao.insertChat(ChatThreadEntity(id = chatId, title = title, createdAt = now))
        _currentChatId.value = chatId
        currentStep.value = AiAssistantStep.STEP1
        return chatId
    }

    suspend fun switchChat(chatId: Long) {
        if (chatDao.getChatById(chatId) == null) return
        _currentChatId.value = chatId
        currentStep.value = AiAssistantStep.STEP1
    }

    suspend fun ask(
        text: String,
        settings: AppSettings,
        profile: RamProfile,
        useGigaChat: Boolean,
        online: Boolean,
    ): String {
        addMessage(text = text, isUser = true)

        val step = decideStep(text)
        currentStep.value = step

        val context = if (useGigaChat) {
            buildAiAssistantContext(text, step)
        } else {
            pdd.search(text, settings.language)
        }

        val prompt = promptBuilder.build(
            userText = text,
            context = context,
            language = settings.language,
            profile = profile,
            step = step,
        )

        val answer = if (useGigaChat) {
            askGigaChat(prompt, settings, online)
        } else {
            askLocal(prompt, profile)
        }

        addAssistantMessage(answer)
        return answer
    }

    suspend fun addAssistantMessage(text: String) {
        addMessage(text = text, isUser = false)
    }

    suspend fun ensureStatusMessage(text: String) {
        val messages = history.first()
        if (messages.isEmpty() || messages.last().text != text) {
            addAssistantMessage(text)
        }
    }

    suspend fun clear() {
        ensureActiveChat()
        chatDao.clear(_currentChatId.value)
        currentStep.value = AiAssistantStep.STEP1
    }

    suspend fun clearAll() {
        chatDao.clearAllMessages()
        chatDao.clearAllChats()
        currentStep.value = AiAssistantStep.STEP1
        _currentChatId.value = 0L
        ensureActiveChat()
    }

    private suspend fun askGigaChat(prompt: String, settings: AppSettings, online: Boolean): String {
        if (!online) {
            return "Сейчас выбран GigaChat, но интернет недоступен. Либо верните соединение, либо переключитесь на локальную модель."
        }

        if (!gigaChat.isConfigured(settings)) {
            return "GigaChat выбран, но не настроен в сборке. Добавьте GIGACHAT_API_PERS в local.properties и пересоберите приложение."
        }

        return gigaChat.ask(prompt, settings).getOrElse { error ->
            "GigaChat сейчас не ответил: ${error.message ?: "неизвестная ошибка"}"
        }
    }

    private suspend fun askLocal(prompt: String, profile: RamProfile): String {
        if (!localEngine.isModelAvailable(profile)) {
            return "Выбрана локальная модель, но GGUF для профиля ${profile.name} не установлена. Скачайте модель в настройках ИИ."
        }

        val loadResult = localEngine.load(profile)
        if (loadResult.isFailure) {
            return "Не удалось загрузить локальную модель: ${loadResult.exceptionOrNull()?.message ?: "неизвестная ошибка"}"
        }

        return localEngine.generate(prompt).getOrElse { error ->
            "Локальная модель не смогла ответить: ${error.message ?: "неизвестная ошибка"}"
        }
    }

    private suspend fun addMessage(text: String, isUser: Boolean) {
        ensureActiveChat()
        chatDao.insert(
            ChatEntity(
                id = System.currentTimeMillis(),
                chatId = _currentChatId.value,
                text = text,
                isUser = isUser,
                createdAt = System.currentTimeMillis(),
            ),
        )
    }

    private fun decideStep(text: String): AiAssistantStep {
        val lower = text.lowercase()
        val chatState = sessionByChatId[_currentChatId.value] ?: SessionState()

        if (chatState.offeredEuro) {
            return when {
                listOf("через приложение", "в приложении", "наше приложение", "нашем приложении").any(lower::contains) -> {
                    sessionByChatId[_currentChatId.value] = chatState.copy(offeredEuro = false)
                    AiAssistantStep.STEP2
                }
                listOf("госуслуги", "помощник осаго", "другое приложение", "стороннее приложение").any(lower::contains) -> {
                    sessionByChatId[_currentChatId.value] = chatState.copy(offeredEuro = false)
                    AiAssistantStep.FILL_EXTERNAL
                }
                listOf("бумаж", "бланк").any(lower::contains) -> {
                    sessionByChatId[_currentChatId.value] = chatState.copy(offeredEuro = false)
                    AiAssistantStep.FILL_EXTERNAL
                }
                listOf("не хочу", "не буду", "отказываюсь", "без европротокола").any(lower::contains) -> {
                    sessionByChatId[_currentChatId.value] = chatState.copy(offeredEuro = false)
                    AiAssistantStep.CONSULTANT_ONLY
                }
                else -> AiAssistantStep.OFFER_EUROPROTOCOL
            }
        }

        if (listOf("пострадав", "ранен", "кров", "травм", "без сознания").any(lower::contains)) {
            return AiAssistantStep.CALL_GIBDD
        }

        if (listOf("дтп", "авар", "столкнов", "машин").any(lower::contains) &&
            listOf("нет пострадав", "без пострадавших", "две машины", "осаго").any(lower::contains)
        ) {
            sessionByChatId[_currentChatId.value] = chatState.copy(offeredEuro = true)
            return AiAssistantStep.OFFER_EUROPROTOCOL
        }

        return when {
            listOf("страхов", "осаго", "выплат", "документ", "уведом").any(lower::contains) ->
                AiAssistantStep.STEP3

            listOf("европротокол", "схема", "бланк", "извещен").any(lower::contains) ->
                AiAssistantStep.STEP2

            listOf("дтп", "авар", "столкнов", "пострад", "гаи", "гибдд").any(lower::contains) ->
                AiAssistantStep.STEP1

            else -> AiAssistantStep.CONSULTANT_ONLY
        }
    }

    private fun isDtpTopic(text: String): Boolean {
        val lower = text.lowercase()
        val topicWords = listOf(
            "дтп", "авар", "столкнов", "осаго", "европротокол", "гибдд", "страхов",
            "выплат", "ущерб", "ремонт", "протокол", "пострадав", "схема",
        )
        return topicWords.any(lower::contains)
    }

    private fun buildAiAssistantContext(text: String, step: AiAssistantStep): List<com.dtp.dtpassist.domain.model.PddArticle> {
        val base = aiAssistantRag.search(text, limit = when (step) {
            AiAssistantStep.STEP1 -> 7
            AiAssistantStep.STEP2 -> 8
            AiAssistantStep.STEP3 -> 7
            else -> 6
        }).toMutableList()

        val lower = text.lowercase()
        val disagreementMode = listOf(
            "разноглас", "не соглас", "не согласен", "винов", "спор", "оспар", "противореч"
        ).any(lower::contains)
        if (disagreementMode) {
            base += aiAssistantRag.searchDisagreement(text, limit = 3)
        }

        val algo = aiAssistantRag.algorithmDoc()
        if (algo != null && base.none { it.id == algo.id }) {
            base.add(0, algo)
        }

        return base.distinctBy { it.id }
    }
}
