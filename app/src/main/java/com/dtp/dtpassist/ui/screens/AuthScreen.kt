package com.dtp.dtpassist.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.dtp.dtpassist.ui.theme.Primary
import com.dtp.dtpassist.ui.theme.TextMuted
import kotlinx.coroutines.launch

@Composable
fun AuthScreen(
    onRegister: suspend (
        lastName: String,
        firstName: String,
        middleName: String,
        contact: String,
        password: String,
        passwordConfirm: String
    ) -> String?,
    onLogin: suspend (contact: String, password: String) -> String?,
) {
    val scope = rememberCoroutineScope()
    var isRegister by rememberSaveable { mutableStateOf(true) }
    var authError by rememberSaveable { mutableStateOf("") }

    var lastName by rememberSaveable { mutableStateOf("") }
    var firstName by rememberSaveable { mutableStateOf("") }
    var middleName by rememberSaveable { mutableStateOf("") }
    var registerContact by rememberSaveable { mutableStateOf("") }
    var registerPassword by rememberSaveable { mutableStateOf("") }
    var registerPasswordConfirm by rememberSaveable { mutableStateOf("") }

    var loginContact by rememberSaveable { mutableStateOf("") }
    var loginPassword by rememberSaveable { mutableStateOf("") }

    val cardShape = RoundedCornerShape(20.dp)

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFFF3F4F6))
            .imePadding()
            .padding(24.dp),
        contentAlignment = Alignment.TopCenter
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = cardShape,
            colors = CardDefaults.cardColors(containerColor = Color.White),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier
                    .padding(24.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = if (isRegister) "Регистрация" else "Вход",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF111827)
                )

                Text(
                    text = if (isRegister) {
                        "Создайте аккаунт для использования ассистента ДТП"
                    } else {
                        "Войдите в аккаунт для продолжения"
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextMuted
                )

                if (isRegister) {
                    LabeledField(
                        label = "Фамилия",
                        value = lastName,
                        onValueChange = { lastName = it },
                        placeholder = "Иванов"
                    )
                    LabeledField(
                        label = "Имя",
                        value = firstName,
                        onValueChange = { firstName = it },
                        placeholder = "Иван"
                    )
                    LabeledField(
                        label = "Отчество",
                        value = middleName,
                        onValueChange = { middleName = it },
                        placeholder = "Иванович"
                    )
                    LabeledField(
                        label = "Email или телефон",
                        value = registerContact,
                        onValueChange = { registerContact = normalizeContactInput(it) },
                        placeholder = "you@example.com или +7XXXXXXXXXX",
                        keyboardType = KeyboardType.Email
                    )
                    LabeledField(
                        label = "Пароль",
                        value = registerPassword,
                        onValueChange = { registerPassword = it },
                        placeholder = "Минимум 8 символов",
                        isPassword = true
                    )
                    LabeledField(
                        label = "Подтверждение пароля",
                        value = registerPasswordConfirm,
                        onValueChange = { registerPasswordConfirm = it },
                        placeholder = "Повторите пароль",
                        isPassword = true
                    )

                    Button(
                        onClick = {
                            scope.launch {
                                authError = onRegister(
                                    lastName,
                                    firstName,
                                    middleName,
                                    registerContact,
                                    registerPassword,
                                    registerPasswordConfirm,
                                ).orEmpty()
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10131A))
                    ) {
                        Text("Зарегистрироваться", color = Color.White, fontWeight = FontWeight.Bold)
                    }

                    TextButton(
                        onClick = {
                            authError = ""
                            isRegister = false
                        },
                        modifier = Modifier.align(Alignment.CenterHorizontally)
                    ) {
                        Text("Уже есть аккаунт? Войти", color = Primary)
                    }
                } else {
                    LabeledField(
                        label = "Email или телефон",
                        value = loginContact,
                        onValueChange = { loginContact = normalizeContactInput(it) },
                        placeholder = "you@example.com или +7XXXXXXXXXX",
                        keyboardType = KeyboardType.Email
                    )
                    if (authError.isNotBlank()) {
                        Text(
                            text = authError,
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFB91C1C)
                        )
                    }
                    LabeledField(
                        label = "Пароль",
                        value = loginPassword,
                        onValueChange = { loginPassword = it },
                        placeholder = "Введите пароль",
                        isPassword = true
                    )

                    Button(
                        onClick = {
                            scope.launch {
                                val loginError = onLogin(
                                    loginContact,
                                    loginPassword,
                                )
                                authError = if (loginError != null) {
                                    "неверно введенные данные для входа"
                                } else {
                                    ""
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(10.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10131A))
                    ) {
                        Text("Войти", color = Color.White, fontWeight = FontWeight.Bold)
                    }

                    TextButton(
                        onClick = {
                            authError = ""
                            isRegister = true
                        },
                        modifier = Modifier.align(Alignment.CenterHorizontally)
                    ) {
                        Text("Нет аккаунта? Зарегистрироваться", color = Primary)
                    }
                }

                if (isRegister && authError.isNotBlank()) {
                    Text(
                        text = authError,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFFB91C1C)
                    )
                }

                Spacer(Modifier.height(2.dp))
            }
        }
    }
}

private fun normalizeContactInput(raw: String): String {
    if (raw.isBlank()) return ""

    // Keep email-like input untouched.
    if (raw.contains("@") || raw.any { it.isLetter() }) return raw

    // Phone mode: auto-prepend '+' and keep only digits after it.
    val digits = raw.filter { it.isDigit() }
    return if (digits.isEmpty()) "+" else "+$digits"
}

@Composable
private fun LabeledField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    keyboardType: KeyboardType = KeyboardType.Text,
    isPassword: Boolean = false
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF111827)
        )
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            placeholder = { Text(placeholder, color = Color(0xFF9CA3AF)) },
            singleLine = true,
            visualTransformation = if (isPassword) PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
            keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFF111827),
                unfocusedBorderColor = Color(0xFFD1D5DB),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
    }
}
