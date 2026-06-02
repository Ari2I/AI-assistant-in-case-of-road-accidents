package com.dtp.dtpassist.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.dtp.dtpassist.ui.theme.*

data class Step(val title: String, val content: String, val important: String? = null)

private val steps = listOf(
    Step(
        "Обеспечьте безопасность",
        "Включите аварийную сигнализацию. Выставьте знак аварийной остановки (15м в городе, 30м за городом). Убедитесь, что нет пострадавших.",
        "Если есть пострадавшие — вызывайте 112 и не трогайте ничего до приезда полиции!"
    ),
    Step(
        "Проверьте условия европротокола",
        "В ДТП только 2 авто. Нет пострадавших. У обоих есть ОСАГО. Ущерб до 400к (с фото) или до 100к (с разногласиями)."
    ),
    Step(
        "Сфотографируйте место ДТП",
        "Общий план с 4 сторон. Повреждения крупным планом. Номера обоих авто. Дорожные знаки и разметку.",
        "Минимум 6-8 фотографий!"
    ),
    Step(
        "Заполните извещение",
        "Заполните лицевую сторону вместе. Укажите время и место. Опишите обстоятельства. Нарисуйте схему. Подпишите оба."
    )
)

@Composable
fun InstructionsScreen() {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Text(
                text = "Инструкции",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = TextMain
            )
            Text(
                text = "Пошаговое руководство при ДТП",
                style = MaterialTheme.typography.bodyMedium,
                color = TextMuted
            )
            Spacer(Modifier.height(16.dp))
        }

        itemsIndexed(steps) { index, step ->
            InstructionStepItem(index + 1, step)
        }
    }
}

@Composable
fun InstructionStepItem(number: Int, step: Step) {
    var expanded by remember { mutableStateOf(number == 1) }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = androidx.compose.foundation.BorderStroke(1.dp, Border)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(32.dp),
                    shape = CircleShape,
                    color = Primary
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text(number.toString(), color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
                Spacer(Modifier.width(12.dp))
                Text(
                    text = step.title,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Icon(
                    if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = null,
                    tint = TextMuted
                )
            }

            AnimatedVisibility(visible = expanded) {
                Column {
                    Spacer(Modifier.height(12.dp))
                    Text(
                        text = step.content,
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFF555555),
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight * 1.4
                    )
                    step.important?.let {
                        Spacer(Modifier.height(12.dp))
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(WarningSoft, RoundedCornerShape(8.dp))
                                .padding(12.dp)
                        ) {
                            Text(it, color = Color(0xFF664400), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
