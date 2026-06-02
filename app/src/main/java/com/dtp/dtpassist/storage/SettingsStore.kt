package com.dtp.dtpassist.storage

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.dtp.dtpassist.domain.model.AppLanguage
import com.dtp.dtpassist.domain.model.RamProfile
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("settings")

data class AppSettings(
    val language: AppLanguage = AppLanguage.RU,
    val profile: RamProfile = RamProfile.BALANCED,
    val autoSpeak: Boolean = true,
    val speechRate: Float = 1.0f,
    val useGigaChat: Boolean = true,
    val forceOffline: Boolean = false,
)

class SettingsStore(private val context: Context) {
    private val languageKey = stringPreferencesKey("language")
    private val profileKey = stringPreferencesKey("profile")
    private val autoSpeakKey = booleanPreferencesKey("auto_speak")
    private val rateKey = floatPreferencesKey("speech_rate")
    private val gigaKey = booleanPreferencesKey("use_gigachat")
    private val forceOfflineKey = booleanPreferencesKey("force_offline")

    val settings = context.dataStore.data.map {
        AppSettings(
            language = AppLanguage.valueOf(it[languageKey] ?: AppLanguage.RU.name),
            profile = RamProfile.valueOf(it[profileKey] ?: RamProfile.BALANCED.name),
            autoSpeak = it[autoSpeakKey] ?: true,
            speechRate = it[rateKey] ?: 1.0f,
            useGigaChat = it[gigaKey] ?: true,
            forceOffline = it[forceOfflineKey] ?: false,
        )
    }

    suspend fun setLanguage(v: AppLanguage) = context.dataStore.edit { it[languageKey] = v.name }
    suspend fun setProfile(v: RamProfile) = context.dataStore.edit { it[profileKey] = v.name }
    suspend fun setAutoSpeak(v: Boolean) = context.dataStore.edit { it[autoSpeakKey] = v }
    suspend fun setSpeechRate(v: Float) = context.dataStore.edit { it[rateKey] = v }
    suspend fun setUseGigaChat(v: Boolean) = context.dataStore.edit { it[gigaKey] = v }
    suspend fun setForceOffline(v: Boolean) = context.dataStore.edit { it[forceOfflineKey] = v }
}
