package com.dtp.dtpassist.domain.model

enum class AppLanguage { RU, EN }
enum class RamProfile(val context: Int) {
    LIGHTWEIGHT(1024),
    BALANCED(1536),
    HIGH_QUALITY(2048)
}

data class ChatMessage(
    val id: Long = System.currentTimeMillis(),
    val text: String,
    val isUser: Boolean,
    val createdAt: Long = System.currentTimeMillis(),
)

data class ChatThread(
    val id: Long,
    val title: String,
    val createdAt: Long,
)

data class AssistantAnswer(
    val shortAnswer: String,
    val doNow: String,
    val clarifyNext: String,
    val voiceVersion: String,
)

data class PddArticle(
    val id: String,
    val title: String,
    val lang: AppLanguage,
    val tags: List<String>,
    val body: String,
)

data class ModelOption(
    val id: String,
    val title: String,
    val profile: RamProfile,
    val url: String,
    val sha256: String,
    val fileName: String,
)

data class DownloadState(
    val isDownloading: Boolean = false,
    val progress: Float = 0f,
    val message: String = "",
)

data class AccidentState(
    val hasInjured: Boolean? = null,
    val conflict: Boolean? = null,
    val cars: String = "",
    val osago: String = "",
    val damage: String = "",
)
