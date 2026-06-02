package com.dtp.dtpassist.pdd_knowledge

import android.content.Context
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.PddArticle
import org.json.JSONArray

class PddKnowledgeRepository(private val context: Context) {
    private var cache: List<PddArticle> = emptyList()

    fun load(): List<PddArticle> {
        if (cache.isNotEmpty()) return cache
        val text = context.assets.open("pdd/pdd_ru_en.json").bufferedReader().use { it.readText() }
        val array = JSONArray(text)
        cache = (0 until array.length()).map { i ->
            val o = array.getJSONObject(i)
            PddArticle(
                id = o.getString("id"),
                title = o.getString("title"),
                lang = if (o.optString("lang") == "en") AppLanguage.EN else AppLanguage.RU,
                tags = o.getJSONArray("tags").let { tags -> (0 until tags.length()).map { tags.getString(it) } },
                body = o.getString("body"),
            )
        }
        return cache
    }

    fun search(query: String, language: AppLanguage, limit: Int = 4): List<PddArticle> {
        val tokens = query.lowercase().split(Regex("\\W+")).filter { it.length > 2 }
        val ranked: List<Pair<PddArticle, Int>> = load()
            .filter { it.lang == language }
            .map { article ->
                val haystack = (article.title + " " + article.tags.joinToString(" ") + " " + article.body).lowercase()
                var tokenScore = 0
                tokens.forEach { token -> if (haystack.contains(token)) tokenScore += 2 }
                var tagScore = 0
                article.tags.forEach { tag -> if (query.lowercase().contains(tag.lowercase())) tagScore += 3 }
                Pair(article, tokenScore + tagScore)
            }
        val found = ranked
            .filter { it.second > 0 }
            .sortedByDescending { it.second }
            .take(limit)
            .map { it.first }
        return if (found.isEmpty()) fallback(language) else found
    }

    private fun fallback(language: AppLanguage): List<PddArticle> = load()
        .filter { it.lang == language && it.tags.any { tag -> tag == "fallback" || tag == "safety" } }
        .take(3)
}
