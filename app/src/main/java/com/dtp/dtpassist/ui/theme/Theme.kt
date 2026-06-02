package com.dtp.dtpassist.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Primary,
    onPrimary = Color.White,
    primaryContainer = PrimarySoft,
    onPrimaryContainer = PrimaryDark,
    
    secondary = Success,
    onSecondary = Color.White,
    secondaryContainer = SuccessSoft,
    onSecondaryContainer = SuccessDark,
    
    tertiary = Info,
    onTertiary = Color.White,
    tertiaryContainer = InfoSoft,
    onTertiaryContainer = Info,
    
    error = Danger,
    onError = Color.White,
    errorContainer = DangerSoft,
    onErrorContainer = DangerDark,
    
    background = Background,
    onBackground = TextMain,
    surface = Surface,
    onSurface = TextMain,
    surfaceVariant = Background,
    onSurfaceVariant = TextMuted,
    outline = Border,
)

@Composable
fun DtpAssistTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = Typography,
        content = content,
    )
}
