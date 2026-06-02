package com.dtp.dtpassist.di

import android.content.Context
import com.dtp.dtpassist.audio.ConnectivityMonitor
import com.dtp.dtpassist.audio.LocationProvider
import com.dtp.dtpassist.data.local.ChatDatabase
import com.dtp.dtpassist.data.network.GigaChatClient
import com.dtp.dtpassist.data.repository.AssistantRepository
import com.dtp.dtpassist.llm.LlamaCppEngine
import com.dtp.dtpassist.llm.ModelManager
import com.dtp.dtpassist.llm.PromptBuilder
import com.dtp.dtpassist.pdd_knowledge.AiAssistantRagRepository
import com.dtp.dtpassist.pdd_knowledge.PddKnowledgeRepository
import com.dtp.dtpassist.storage.SettingsStore
import com.dtp.dtpassist.storage.ProfileStore
import com.dtp.dtpassist.stt.OfflineSpeechRecognizer
import com.dtp.dtpassist.tts.OfflineTts

class AppContainer(context: Context) {
    private val app = context.applicationContext
    private val db = ChatDatabase.create(app)
    val settings = SettingsStore(app)
    val profile = ProfileStore(app)
    val modelManager = ModelManager(app)
    val stt = OfflineSpeechRecognizer(app)
    val tts = OfflineTts(app)
    val connectivity = ConnectivityMonitor(app)
    val location = LocationProvider(app)
    val pdd = PddKnowledgeRepository(app)
    val aiAssistantRag = AiAssistantRagRepository(app)
    val gigaChat = GigaChatClient()
    val assistant = AssistantRepository(db.chatDao(), pdd, aiAssistantRag, LlamaCppEngine(app), PromptBuilder(), gigaChat)
}
