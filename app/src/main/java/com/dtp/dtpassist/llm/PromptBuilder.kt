package com.dtp.dtpassist.llm

import com.dtp.dtpassist.domain.model.AiAssistantStep
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.PddArticle
import com.dtp.dtpassist.domain.model.RamProfile

class PromptBuilder {
    fun build(userText: String, context: List<PddArticle>, language: AppLanguage, profile: RamProfile, step: AiAssistantStep): String {
        val lang = if (language == AppLanguage.RU) "Russian" else "English"
        val pdd = context.joinToString("\n\n") { "[${it.id}] ${it.title}\n${it.body}" }
        
        val stepInstruction = when (step) {
            AiAssistantStep.STEP1 -> """
                CURRENT STEP: Step 1 - Fact Gathering.
                Objective: Ensure safety, check for injuries, count participants, check for insurance, identify disagreements.
                If anyone is injured, IMMEDIATELY tell them to call 112/103.
                Ask one question at a time.
                If Europrotocol is possible, explain limits and suggest it.
            """.trimIndent()
            AiAssistantStep.OFFER_EUROPROTOCOL -> """
                CURRENT STEP: Offering Europrotocol.
                Objective: Explain limits (400k with app, 100k without) and ask how they want to proceed (our app, other app, or paper).
            """.trimIndent()
            AiAssistantStep.STEP2 -> """
                CURRENT STEP: Step 2 - Filling the Protocol.
                Objective: Guide user through date/time, location, vehicles A/B, damage, circumstances, and scheme.
                Reformulate user input into official style.
            """.trimIndent()
            AiAssistantStep.STEP3 -> """
                CURRENT STEP: Step 3 - Insurance Interaction.
                Objective: Explain 5-day deadline for notification, 15-day no-repair rule, and required documents.
            """.trimIndent()
            else -> """
                CURRENT STEP: Consultant Mode.
                Objective: Answer questions about traffic rules and OSAGO briefly and naturally.
            """.trimIndent()
        }

        return """
            SYSTEM:
            You are a calm driving assistant. Answer in $lang.
            Follow the algorithm for DTP assistance.
            If the question is about Russian traffic rules or a crash, use RETRIEVED_PDD_CONTEXT.
            Do not pretend to be a lawyer, police officer, or official authority.
            Be practical and concise.

            $stepInstruction

            RULES:
            - No section headers.
            - 1-5 short sentences.
            - Device profile: ${profile.name}.

            RETRIEVED_PDD_CONTEXT:
            $pdd

            USER:
            $userText
        """.trimIndent()
    }
}
