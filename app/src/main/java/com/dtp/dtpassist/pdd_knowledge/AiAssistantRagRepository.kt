package com.dtp.dtpassist.pdd_knowledge

import android.content.Context
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.PddArticle
import java.util.Locale

class AiAssistantRagRepository(private val context: Context) {
    private var cache: List<PddArticle> = emptyList()

    fun search(query: String, limit: Int = 6): List<PddArticle> {
        val docs = loadMainDocs()
        if (docs.isEmpty()) return withAlgorithm(emptyList(), load())
        val found = rank(docs, query, limit)
        if (found.isNotEmpty()) return withAlgorithm(found, load())
        return withAlgorithm(docs.take(3), load())
    }

    fun searchDisagreement(query: String, limit: Int = 3): List<PddArticle> {
        val docs = loadDisagreementDocs()
        if (docs.isEmpty()) return emptyList()
        val found = rank(docs, query, limit)
        return if (found.isNotEmpty()) found else docs.take(1)
    }

    fun algorithmDoc(): PddArticle? = load().firstOrNull { it.id.contains("ai-algorithm", ignoreCase = true) }

    private fun rank(docs: List<PddArticle>, query: String, limit: Int): List<PddArticle> {
        val tokens = query.lowercase(Locale.getDefault()).split(Regex("\\W+")).filter { it.length > 2 }
        val ranked = docs.map { doc ->
            val haystack = (doc.title + " " + doc.body).lowercase(Locale.getDefault())
            var score = 0
            tokens.forEach { token ->
                if (haystack.contains(token)) score += 2
                if (doc.title.lowercase(Locale.getDefault()).contains(token)) score += 3
            }
            if (doc.id.contains("ai-algorithm", ignoreCase = true)) score += 2
            Pair(doc, score)
        }
        return ranked.filter { it.second > 0 }.sortedByDescending { it.second }.take(limit).map { it.first }
    }

    private fun loadMainDocs(): List<PddArticle> =
        load().filterNot { it.id.contains("Docs_disagreement", ignoreCase = true) }

    private fun loadDisagreementDocs(): List<PddArticle> =
        load().filter { it.id.contains("Docs_disagreement", ignoreCase = true) }

    private fun withAlgorithm(items: List<PddArticle>, allDocs: List<PddArticle>): List<PddArticle> {
        val algo = allDocs.firstOrNull { it.id.contains("ai-algorithm", ignoreCase = true) }
        if (algo == null) return items
        if (items.any { it.id == algo.id }) return items
        return listOf(algo) + items
    }

    private fun load(): List<PddArticle> {
        if (cache.isNotEmpty()) return cache
        val files = mutableListOf<String>()
        collectMarkdownFiles("", files)

        cache = files.mapNotNull { path ->
            runCatching {
                val text = context.assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }
                PddArticle(
                    id = path,
                    title = path.substringAfterLast('/').removeSuffix(".md"),
                    lang = AppLanguage.RU,
                    tags = listOf("ai_assistant_rag"),
                    body = text,
                )
            }.getOrNull()
        }

        return cache
    }

    private fun collectMarkdownFiles(path: String, out: MutableList<String>) {
        val children = context.assets.list(path).orEmpty()
        children.forEach { name ->
            val child = if (path.isBlank()) name else "$path/$name"
            val grandChildren = context.assets.list(child).orEmpty()
            if (grandChildren.isNotEmpty()) {
                collectMarkdownFiles(child, out)
            } else if (child.endsWith(".md", ignoreCase = true)) {
                out += child
            }
        }
    }
}
