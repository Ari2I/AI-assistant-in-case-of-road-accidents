package com.dtp.dtpassist.storage

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.authDataStore by preferencesDataStore("auth")

data class AuthState(
    val isLoggedIn: Boolean = false,
    val lastName: String = "",
    val firstName: String = "",
    val middleName: String = "",
    val contact: String = "",
)

class AuthStore(private val context: Context) {
    private val isLoggedInKey = booleanPreferencesKey("is_logged_in")
    private val lastNameKey = stringPreferencesKey("last_name")
    private val firstNameKey = stringPreferencesKey("first_name")
    private val middleNameKey = stringPreferencesKey("middle_name")
    private val contactKey = stringPreferencesKey("contact")
    private val passwordKey = stringPreferencesKey("password")

    val auth = context.authDataStore.data.map {
        AuthState(
            isLoggedIn = it[isLoggedInKey] ?: false,
            lastName = it[lastNameKey].orEmpty(),
            firstName = it[firstNameKey].orEmpty(),
            middleName = it[middleNameKey].orEmpty(),
            contact = it[contactKey].orEmpty(),
        )
    }

    suspend fun register(
        lastName: String,
        firstName: String,
        middleName: String,
        contact: String,
        password: String,
        passwordConfirm: String,
    ): String? {
        if (lastName.isBlank() || firstName.isBlank() || middleName.isBlank()) return "Заполните фамилию, имя и отчество."
        if (!isValidContact(contact)) return "Введите корректный email или телефон в формате +7XXXXXXXXXX."
        if (password.length < 8) return "Пароль должен быть не короче 8 символов."
        if (password != passwordConfirm) return "Пароли не совпадают."

        context.authDataStore.edit {
            it[lastNameKey] = lastName.trim()
            it[firstNameKey] = firstName.trim()
            it[middleNameKey] = middleName.trim()
            it[contactKey] = contact.trim()
            it[passwordKey] = password
            it[isLoggedInKey] = true
        }
        return null
    }

    suspend fun login(contact: String, password: String): String? {
        if (!isValidContact(contact)) return "Введите корректный email или телефон."
        if (password.isBlank()) return "Введите пароль."

        val prefs = context.authDataStore.data.first()
        val savedContact = prefs[contactKey].orEmpty()
        val savedPassword = prefs[passwordKey].orEmpty()

        if (savedContact.isBlank() || savedPassword.isBlank()) return "Аккаунт не найден. Сначала зарегистрируйтесь."
        if (savedContact != contact.trim() || savedPassword != password) return "Неверный логин или пароль."

        context.authDataStore.edit { it[isLoggedInKey] = true }
        return null
    }

    suspend fun logout() {
        context.authDataStore.edit { it[isLoggedInKey] = false }
    }

    suspend fun changePassword(oldPassword: String, newPassword: String, newPasswordConfirm: String): String? {
        if (oldPassword.isBlank()) return "Введите старый пароль."
        if (newPassword.length < 8) return "Новый пароль должен быть не короче 8 символов."
        if (newPassword != newPasswordConfirm) return "Новые пароли не совпадают."

        val prefs = context.authDataStore.data.first()
        val savedPassword = prefs[passwordKey].orEmpty()
        if (savedPassword.isBlank()) return "Пароль не найден. Сначала зарегистрируйтесь."
        if (savedPassword != oldPassword) return "Старый пароль введен неверно."

        context.authDataStore.edit { it[passwordKey] = newPassword }
        return null
    }

    private fun isValidContact(value: String): Boolean {
        val v = value.trim()
        val emailRegex = Regex("^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$")
        val phoneRegex = Regex("^\\+7\\d{10}$")
        return emailRegex.matches(v) || phoneRegex.matches(v)
    }
}
