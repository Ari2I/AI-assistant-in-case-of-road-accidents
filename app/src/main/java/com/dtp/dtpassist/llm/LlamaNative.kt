package com.dtp.dtpassist.llm

object LlamaNative {
    init {
        System.loadLibrary("dtpassist_llama")
    }

    external fun loadModel(path: String, contextSize: Int, threads: Int): Long
    external fun generate(handle: Long, prompt: String, maxTokens: Int): String
    external fun release(handle: Long)
}
