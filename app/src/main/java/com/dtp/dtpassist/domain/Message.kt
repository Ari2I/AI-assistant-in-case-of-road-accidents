package com.dtp.dtpassist.domain

data class Message(
    val id: String,
    val chatId: String,
    val text: String,
    val isUser: Boolean,
    val timestamp: Long
)