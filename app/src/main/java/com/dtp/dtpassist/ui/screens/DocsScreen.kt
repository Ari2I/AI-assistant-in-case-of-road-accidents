package com.dtp.dtpassist.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.HealthAndSafety
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.dtp.dtpassist.storage.UserProfile
import com.dtp.dtpassist.ui.components.GradientCard
import com.dtp.dtpassist.ui.components.SaaSCard
import com.dtp.dtpassist.ui.theme.*

@Composable
fun DocsScreen(
    profile: UserProfile,
    onOsagoEdit: () -> Unit,
    onVudEdit: () -> Unit,
    onStsEdit: () -> Unit,
    onDiagEdit: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Text(
                text = "Ваши документы",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = TextMain
            )
        }

        item {
            InsuranceCard(
                osago = profile.osago,
                onClick = onOsagoEdit,
            )
        }

        item {
            SaaSCard(title = "Оценка ущерба") {
                DamageItem("Передний бампер", 0f, 0f, Warning)
                DamageItem("Капот", 0f, 0f, Warning)
                DamageItem("Левое крыло", 0f, 0f, Success)

                HorizontalDivider(Modifier.padding(vertical = 8.dp), color = Border)

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Итого:", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                    Text("0 ₽", color = Primary, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineSmall)
                }
            }
        }

        item {
            DocListItem(
                "Водительское удостоверение",
                profile.driverLicense.ifBlank { "Не заполнено" },
                Icons.Default.Description,
                Warning,
                onClick = onVudEdit
            )
        }
        item {
            DocListItem(
                "СТС",
                profile.sts.ifBlank { "Не заполнено" },
                Icons.Default.Description,
                Primary,
                onClick = onStsEdit
            )
        }
        item {
            DocListItem(
                "Диагностическая карта",
                profile.diagnosticCard.ifBlank { "Не заполнено" },
                Icons.Default.HealthAndSafety,
                Success,
                onClick = onDiagEdit
            )
        }
    }
}

@Composable
fun InsuranceCard(osago: String, onClick: () -> Unit) {
    GradientCard(modifier = Modifier.clickable { onClick() }) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Полис ОСАГО", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                Surface(
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp),
                    color = Color.White.copy(alpha = 0.2f)
                ) {
                    Text(
                        if (osago.isBlank()) "Не заполнено" else "Заполнено",
                        color = Color.White,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall
                    )
                }
            }

            Spacer(Modifier.height(24.dp))

            InsuranceField("Номер полиса", osago)
        }
    }
}

@Composable
fun InsuranceField(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, color = Color.White.copy(alpha = 0.7f), style = MaterialTheme.typography.bodySmall)
        Text(value, color = Color.White, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
fun DamageItem(label: String, amount: Float, progress: Float, color: Color) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text("${amount.toInt()} ₽", fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(androidx.compose.foundation.shape.CircleShape),
            color = color,
            trackColor = Border
        )
    }
}

@Composable
fun DocListItem(title: String, desc: String, icon: ImageVector, iconColor: Color, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(16.dp),
        color = Color.White,
        border = androidx.compose.foundation.BorderStroke(1.dp, Border)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Surface(
                modifier = Modifier.size(48.dp),
                shape = RoundedCornerShape(12.dp),
                color = iconColor.copy(alpha = 0.1f)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(icon, contentDescription = null, tint = iconColor)
                }
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyLarge)
                Text(desc, color = TextMuted, style = MaterialTheme.typography.bodySmall)
            }
            Icon(Icons.Default.Edit, contentDescription = null, tint = TextMuted, modifier = Modifier.size(20.dp))
        }
    }
}
