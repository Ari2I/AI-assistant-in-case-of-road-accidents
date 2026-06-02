package com.dtp.dtpassist

import com.dtp.dtpassist.domain.model.AiAssistantStep
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.PddArticle
import com.dtp.dtpassist.domain.model.RamProfile
import com.dtp.dtpassist.llm.PromptBuilder
import org.junit.Assert.assertTrue
import org.junit.Test

class PromptBuilderTest {
    @Test
    fun promptContainsSafetyAndRetrievedContext() {
        val prompt = PromptBuilder().build(
            userText = "Есть пострадавшие?",
            context = listOf(PddArticle("x", "ДТП", AppLanguage.RU, listOf("112"), "Вызвать 112")),
            language = AppLanguage.RU,
            profile = RamProfile.LIGHTWEIGHT,
            step = AiAssistantStep.STEP1
        )
        assertTrue(prompt.contains("Вызвать 112"))
        assertTrue(prompt.contains("LIGHTWEIGHT"))
    }
}
