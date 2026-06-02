package com.dtp.dtpassist.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Phone
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.dtp.dtpassist.storage.UserProfile
import com.dtp.dtpassist.ui.chat.AssistantViewModel
import com.dtp.dtpassist.ui.theme.Border
import com.dtp.dtpassist.ui.theme.Danger
import com.dtp.dtpassist.ui.theme.Primary
import com.dtp.dtpassist.ui.theme.Success
import com.dtp.dtpassist.ui.theme.TextMuted
import com.dtp.dtpassist.ui.theme.Warning

@Composable
fun ProfileScreen(
    profile: UserProfile,
    vm: AssistantViewModel,
    onEditPassport: () -> Unit,
    onEditPhone: () -> Unit,
    onHistoryClick: () -> Unit,
    onAiSettingsClick: () -> Unit,
    onChangePasswordClick: () -> Unit,
    onLogoutClick: () -> Unit,
    onSosClick: () -> Unit,
    onInsuranceClick: () -> Unit,
    onEditInsurancePhone: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { ProfileHeader(profile) }
        item { EmergencyContacts(profile = profile, onSosClick = onSosClick, onInsuranceClick = onInsuranceClick, onEditInsurancePhone = onEditInsurancePhone) }
        item {
            ProfileTabsSection(
                profile = profile,
                onHistoryClick = onHistoryClick,
                onAiSettingsClick = onAiSettingsClick,
                onEditPassport = onEditPassport,
                onEditPhone = onEditPhone,
            )
        }
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(24.dp))
                    .background(Color.White),
            ) {
                ProfileMenuItem("Изменить пароль", Icons.Default.Lock, Warning, onClick = onChangePasswordClick)
                HorizontalDivider(color = Border, thickness = 0.5.dp)
                ProfileMenuItem("Выйти", Icons.AutoMirrored.Filled.ExitToApp, Danger, onClick = onLogoutClick)
            }
        }
    }
}

@Composable
fun ProfileHeader(profile: UserProfile) {
    val fullName = listOf(profile.lastName, profile.firstName, profile.middleName).filter { it.isNotBlank() }.joinToString(" ")
        .ifBlank { "Пользователь" }

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Surface(
            modifier = Modifier.size(100.dp),
            shape = CircleShape,
            color = Primary,
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = fullName.firstOrNull()?.toString() ?: "U",
                    color = Color.White,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
        Spacer(Modifier.height(16.dp))
        Text(
            fullName,
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
        )
        Text(
            profile.email,
            color = TextMuted,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
fun ProfileTabsSection(
    profile: UserProfile,
    onHistoryClick: () -> Unit,
    onAiSettingsClick: () -> Unit,
    onEditPassport: () -> Unit,
    onEditPhone: () -> Unit,
) {
    var personalDataExpanded by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.White)
            .padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ProfileMenuItem("История чатов", Icons.Default.History, Primary) {
            onHistoryClick()
        }
        ProfileMenuItem("Настройки ИИ", Icons.Default.Settings, Success) {
            onAiSettingsClick()
        }
        ProfileMenuItem(
            "Персональные данные",
            Icons.Default.Person,
            Warning,
            trailingIcon = if (personalDataExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
        ) {
            personalDataExpanded = !personalDataExpanded
        }

        if (personalDataExpanded) {
            PersonalDataSection(profile = profile, onEditPassport = onEditPassport, onEditPhone = onEditPhone)
        }
    }
}

@Composable
fun PersonalDataSection(profile: UserProfile, onEditPassport: () -> Unit, onEditPhone: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        PassportCard(profile = profile, onClick = onEditPassport)
        EditableProfileField(
            label = "Номер телефона",
            value = profile.phone.ifBlank { "Не заполнено" },
            onClick = onEditPhone,
        )
        if (profile.email.isNotBlank()) {
            OutlinedTextField(
                value = profile.email,
                onValueChange = {},
                label = { Text("Почта") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                readOnly = true,
            )
        }
    }
}

@Composable
private fun EditableProfileField(label: String, value: String, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(12.dp),
        color = Color.White,
        border = androidx.compose.foundation.BorderStroke(1.dp, Border),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = TextMuted)
            Spacer(Modifier.height(2.dp))
            Text(value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
fun PassportCard(profile: UserProfile, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 6.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFF8E7E1)),
        ) {
            Canvas(modifier = Modifier.matchParentSize()) {
                val step = 18.dp.toPx()
                var x = 0f
                while (x < size.width) {
                    drawLine(
                        color = Color(0x11A1887F),
                        start = Offset(x, 0f),
                        end = Offset(x, size.height),
                        strokeWidth = 1f,
                    )
                    x += step
                }
                var y = 0f
                while (y < size.height) {
                    drawLine(
                        color = Color(0x11A1887F),
                        start = Offset(0f, y),
                        end = Offset(size.width, y),
                        strokeWidth = 1f,
                    )
                    y += step
                }
            }

            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    "РОССИЙСКАЯ ФЕДЕРАЦИЯ",
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 1.5.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                PassportField("Фамилия", profile.lastName)
                PassportField("Имя", profile.firstName)
                PassportField("Отчество", profile.middleName)
                PassportField(
                    "Паспорт выдан",
                    profile.passportIssuedBy,
                )
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Column(modifier = Modifier.weight(1f)) { PassportField("Дата выдачи", profile.passportIssueDate) }
                    Column(modifier = Modifier.weight(1f)) { PassportField("Код подразделения", profile.passportUnitCode) }
                }
                PassportField("Серия и номер", profile.passportSeriesNumber)
            }
        }
    }
}

@Composable
fun PassportField(label: String, value: String) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = Color(0xFF7A1F2B),
            fontSize = 10.sp,
            fontStyle = FontStyle.Italic,
        )
        Text(
            text = value.uppercase(),
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF2F2A25),
            fontFamily = FontFamily.Monospace,
        )
        HorizontalDivider(color = Color(0xFFB98E84), thickness = 1.dp)
    }
}

@Composable
fun EmergencyContacts(
    profile: UserProfile,
    onSosClick: () -> Unit,
    onInsuranceClick: () -> Unit,
    onEditInsurancePhone: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Color.White)
            .padding(16.dp),
    ) {
        Text("Экстренные контакты", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        EmergencyItem("Служба спасения", "112", Icons.Default.Call, Danger, onCall = onSosClick)
        EmergencyItem(
            "Страховая компания",
            profile.insurancePhone.ifBlank { "8 800 100-20-00" },
            Icons.Default.Phone,
            Success,
            onCall = onInsuranceClick,
            onEdit = onEditInsurancePhone,
        )
    }
}

@Composable
fun EmergencyItem(
    name: String,
    phone: String,
    icon: ImageVector,
    color: Color,
    onCall: () -> Unit,
    onEdit: (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(modifier = Modifier.size(40.dp), shape = CircleShape, color = color.copy(alpha = 0.1f)) {
            Box(contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
            }
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(name, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
            Text(phone, color = TextMuted, style = MaterialTheme.typography.bodySmall)
        }
        if (onEdit != null) {
            IconButton(onClick = onEdit) {
                Icon(Icons.Default.Settings, contentDescription = null, tint = TextMuted)
            }
        }
        IconButton(onClick = onCall) {
            Icon(Icons.Default.Call, contentDescription = null, tint = Success)
        }
    }
}

@Composable
fun ProfileMenuItem(
    text: String,
    icon: ImageVector,
    color: Color,
    trailingIcon: ImageVector = Icons.Default.ChevronRight,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(modifier = Modifier.size(40.dp), shape = RoundedCornerShape(10.dp), color = color.copy(alpha = 0.1f)) {
            Box(contentAlignment = Alignment.Center) {
                Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
            }
        }
        Spacer(Modifier.width(16.dp))
        Text(text, modifier = Modifier.weight(1f), fontWeight = FontWeight.Medium)
        Icon(trailingIcon, contentDescription = null, tint = TextMuted)
    }
}
