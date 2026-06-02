package com.dtp.dtpassist.ui.app

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.dtp.dtpassist.di.AppContainer
import com.dtp.dtpassist.domain.model.RamProfile
import com.dtp.dtpassist.storage.AppSettings
import com.dtp.dtpassist.storage.AuthStore
import com.dtp.dtpassist.storage.ProfileStore
import com.dtp.dtpassist.storage.UserProfile
import com.dtp.dtpassist.ui.chat.AssistantViewModel
import com.dtp.dtpassist.ui.screens.ChatScreen
import com.dtp.dtpassist.ui.screens.ConstructorScreen
import com.dtp.dtpassist.ui.screens.DocsScreen
import com.dtp.dtpassist.ui.screens.InstructionsScreen
import com.dtp.dtpassist.ui.screens.ProfileScreen
import com.dtp.dtpassist.ui.screens.AuthScreen
import com.dtp.dtpassist.ui.theme.Background
import com.dtp.dtpassist.ui.theme.Danger
import com.dtp.dtpassist.ui.theme.DangerSoft
import com.dtp.dtpassist.ui.theme.Primary
import com.dtp.dtpassist.ui.theme.PrimaryDark
import com.dtp.dtpassist.ui.theme.PrimarySoft
import com.dtp.dtpassist.ui.theme.Success
import com.dtp.dtpassist.ui.theme.TextMuted
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

internal enum class MainTab(val title: String, val icon: ImageVector) {
    Chat("Чат", Icons.Default.ChatBubble),
    Docs("Документы", Icons.Default.Description),
    Instr("Инструкция", Icons.AutoMirrored.Filled.MenuBook),
    Profile("Профиль", Icons.Default.Person),
}

@Composable
fun AccidentAssistantApp() {
    val context = LocalContext.current
    val authStore = remember(context) { AuthStore(context) }
    val profileStore = remember(context) { ProfileStore(context) }
    val vm: AssistantViewModel = viewModel(factory = SimpleVmFactory { AssistantViewModel(AppContainer(context)) })
    val authState by authStore.auth.collectAsState(initial = com.dtp.dtpassist.storage.AuthState())
    val state by vm.state.collectAsState()
    val download by vm.download.collectAsState()
    var currentTab by remember { mutableStateOf(MainTab.Chat) }
    var isConstructorOpen by remember { mutableStateOf(false) }
    var showPassportEditor by remember { mutableStateOf(false) }
    var showPhoneEditor by remember { mutableStateOf(false) }
    var showInsurancePhoneEditor by remember { mutableStateOf(false) }
    var showOsagoEditor by remember { mutableStateOf(false) }
    var showVudEditor by remember { mutableStateOf(false) }
    var showStsEditor by remember { mutableStateOf(false) }
    var showDiagEditor by remember { mutableStateOf(false) }
    var showAiSettings by remember { mutableStateOf(false) }
    var showChatHistory by remember { mutableStateOf(false) }
    var showChangePasswordDialog by remember { mutableStateOf(false) }
    var showNotificationsDialog by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    fun dialPhone(number: String) {
        runCatching {
            context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number")))
        }.onFailure {
            scope.launch {
                snackbarHostState.showSnackbar("Не удалось открыть набор номера")
            }
        }
    }

    if (!authState.isLoggedIn) {
        AuthScreen(
            onRegister = { lastName, firstName, middleName, contact, password, passwordConfirm ->
                val registerError = authStore.register(lastName, firstName, middleName, contact, password, passwordConfirm)
                if (registerError == null) {
                    val normalizedContact = contact.trim()
                    val isPhone = normalizedContact.startsWith("+7")
                    profileStore.save(
                        state.profile.copy(
                            firstName = firstName.trim(),
                            lastName = lastName.trim(),
                            middleName = middleName.trim(),
                            phone = if (isPhone) normalizedContact else "",
                            email = if (isPhone) "" else normalizedContact,
                        ),
                    )
                }
                registerError
            },
            onLogin = { contact, password ->
                val loginError = authStore.login(contact, password)
                if (loginError == null) {
                    if (state.profile.firstName.isBlank() && authState.firstName.isNotBlank()) {
                        profileStore.save(
                            state.profile.copy(
                                firstName = authState.firstName,
                                lastName = authState.lastName,
                                middleName = authState.middleName,
                                email = state.profile.email.ifBlank { authState.contact.takeIf { "@" in it }.orEmpty() },
                                phone = state.profile.phone.ifBlank { authState.contact.takeIf { it.startsWith("+7") }.orEmpty() },
                            ),
                        )
                    }
                }
                loginError
            }
        )
        return
    }

    if (showPassportEditor) {
        PassportEditorDialog(
            profile = state.profile,
            onSave = {
                vm.saveProfile(it)
                showPassportEditor = false
            },
            onDismiss = { showPassportEditor = false },
        )
    }
    if (showPhoneEditor) {
        SingleFieldEditorDialog(
            title = "Номер телефона",
            label = "Номер телефона",
            initialValue = state.profile.phone,
            onSave = { vm.saveProfile(state.profile.copy(phone = it)) },
            onDismiss = { showPhoneEditor = false },
        )
    }
    if (showInsurancePhoneEditor) {
        SingleFieldEditorDialog(
            title = "Номер страховой",
            label = "Номер страховой компании",
            initialValue = state.profile.insurancePhone,
            onSave = { vm.saveProfile(state.profile.copy(insurancePhone = it)) },
            onDismiss = { showInsurancePhoneEditor = false },
        )
    }
    if (showOsagoEditor) {
        SingleFieldEditorDialog(
            title = "Полис ОСАГО",
            label = "Номер полиса ОСАГО",
            initialValue = state.profile.osago,
            onSave = { vm.saveProfile(state.profile.copy(osago = it)) },
            onDismiss = { showOsagoEditor = false },
        )
    }
    if (showVudEditor) {
        SingleFieldEditorDialog(
            title = "Водительское удостоверение",
            label = "Данные ВУ",
            initialValue = state.profile.driverLicense,
            onSave = { vm.saveProfile(state.profile.copy(driverLicense = it)) },
            onDismiss = { showVudEditor = false },
        )
    }
    if (showStsEditor) {
        SingleFieldEditorDialog(
            title = "СТС",
            label = "Данные СТС",
            initialValue = state.profile.sts,
            onSave = { vm.saveProfile(state.profile.copy(sts = it)) },
            onDismiss = { showStsEditor = false },
        )
    }
    if (showDiagEditor) {
        SingleFieldEditorDialog(
            title = "Диагностическая карта",
            label = "Данные карты",
            initialValue = state.profile.diagnosticCard,
            onSave = { vm.saveProfile(state.profile.copy(diagnosticCard = it)) },
            onDismiss = { showDiagEditor = false },
        )
    }

    fun showNotImplemented(name: String) {
        scope.launch {
            snackbarHostState.showSnackbar("Функция \"$name\" пока в разработке")
        }
    }

    if (showAiSettings) {
        AiSettingsDialog(
            settings = state.settings,
            gigaConfigured = state.gigaConfigured,
            offlineModelInstalled = state.offlineModelInstalled,
            downloadMessage = download.message,
            onUseGigaChatChange = vm::setUseGigaChat,
            onProfileChange = vm::setProfile,
            onDownloadLocalModel = vm::downloadAi,
            onDeleteLocalModel = vm::deleteAi,
            onDismiss = { showAiSettings = false },
        )
    }

    if (showChatHistory) {
        ChatHistoryDialog(
            chats = state.chats,
            currentChatId = state.currentChatId,
            onSelectChat = {
                vm.switchChat(it)
                showChatHistory = false
                currentTab = MainTab.Chat
            },
            onCreateNewChat = {
                vm.createNewChat()
                showChatHistory = false
                currentTab = MainTab.Chat
            },
            onClearAll = { vm.clearAllChatsHistory() },
            onDismiss = { showChatHistory = false },
        )
    }
    if (showChangePasswordDialog) {
        ChangePasswordDialog(
            onSubmit = { oldPassword, newPassword, repeatPassword ->
                scope.launch {
                    val error = authStore.changePassword(oldPassword, newPassword, repeatPassword)
                    if (error == null) {
                        showChangePasswordDialog = false
                        snackbarHostState.showSnackbar("Пароль успешно изменен")
                    } else {
                        snackbarHostState.showSnackbar(error)
                    }
                }
            },
            onDismiss = { showChangePasswordDialog = false },
        )
    }
    if (showNotificationsDialog) {
        NotificationsDialog(onDismiss = { showNotificationsDialog = false })
    }

    Scaffold(
        containerColor = Background,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            if (!isConstructorOpen) {
                PremiumHeader(
                    online = state.online,
                    downloading = download.isDownloading,
                    progress = download.progress,
                    message = download.message,
                    onSosClick = { dialPhone("112") },
                    onNotificationsClick = { showNotificationsDialog = true },
                )
            }
        },
        bottomBar = {
            if (!isConstructorOpen) {
                SaaSBottomBar(currentTab) { currentTab = it }
            }
        },
    ) { padding ->
        Box(modifier = Modifier.padding(if (isConstructorOpen) PaddingValues(0.dp) else padding)) {
            Crossfade(targetState = currentTab, label = "ScreenTransition") { tab ->
                when (tab) {
                    MainTab.Chat -> ChatScreen(state, vm, onOpenConstructor = { isConstructorOpen = true })
                    MainTab.Docs -> DocsScreen(
                        profile = state.profile,
                        onOsagoEdit = { showOsagoEditor = true },
                        onVudEdit = { showVudEditor = true },
                        onStsEdit = { showStsEditor = true },
                        onDiagEdit = { showDiagEditor = true },
                    )
                    MainTab.Instr -> InstructionsScreen()
                    MainTab.Profile -> ProfileScreen(
                        profile = state.profile,
                        vm = vm,
                        onEditPassport = { showPassportEditor = true },
                        onEditPhone = { showPhoneEditor = true },
                        onHistoryClick = { showChatHistory = true },
                        onAiSettingsClick = { showAiSettings = true },
                        onChangePasswordClick = { showChangePasswordDialog = true },
                        onLogoutClick = { scope.launch { authStore.logout() } },
                        onSosClick = { dialPhone("112") },
                        onInsuranceClick = { dialPhone(state.profile.insurancePhone.ifBlank { "88001002000" }) },
                        onEditInsurancePhone = { showInsurancePhoneEditor = true },
                    )
                }
            }

            if (isConstructorOpen) {
                ConstructorScreen(onClose = { isConstructorOpen = false })
            }
        }
    }
}

@Composable
fun PremiumHeader(
    online: Boolean,
    downloading: Boolean,
    progress: Float,
    message: String,
    onSosClick: () -> Unit,
    onNotificationsClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF96BD47))
            .statusBarsPadding()
            .padding(16.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text(
                    text = "DtpAssist",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(40.dp),
                    shape = RoundedCornerShape(12.dp),
                    color = DangerSoft,
                    onClick = onSosClick,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Text("SOS", color = Danger, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                }
                Spacer(Modifier.width(8.dp))
                Surface(
                    modifier = Modifier.size(40.dp),
                    shape = RoundedCornerShape(12.dp),
                    color = PrimarySoft,
                    onClick = onNotificationsClick,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            Icons.Default.Notifications,
                            contentDescription = null,
                            tint = Primary,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
            }
        }

        if (downloading) {
            Spacer(Modifier.height(12.dp))
            DownloadProgress(progress, message)
        }
    }
}

@Composable
fun DownloadProgress(progress: Float, message: String) {
    val animatedProgress by animateFloatAsState(targetValue = progress, label = "DownloadProgress")

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(PrimarySoft, RoundedCornerShape(12.dp))
            .padding(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("Р—Р°РіСЂСѓР·РєР° РР РјРѕРґРµР»Рё", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Text("${(progress * 100).toInt()}%", style = MaterialTheme.typography.labelMedium)
        }
        Spacer(Modifier.height(8.dp))
        LinearProgressIndicator(
            progress = { animatedProgress },
            modifier = Modifier
                .fillMaxWidth()
                .height(6.dp)
                .clip(androidx.compose.foundation.shape.CircleShape),
            color = Primary,
            trackColor = Color.White,
        )
        if (message.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(message, style = MaterialTheme.typography.labelSmall, color = PrimaryDark)
        }
    }
}

@Composable
internal fun SaaSBottomBar(currentTab: MainTab, onTabSelected: (MainTab) -> Unit) {
    NavigationBar(
        containerColor = Color.White,
        tonalElevation = 8.dp,
        modifier = Modifier
            .fillMaxWidth()
            .navigationBarsPadding(),
    ) {
        MainTab.entries.forEach { tab ->
            val selected = currentTab == tab
            NavigationBarItem(
                selected = selected,
                onClick = { onTabSelected(tab) },
                icon = {
                    Icon(
                        imageVector = tab.icon,
                        contentDescription = tab.title,
                        tint = if (selected) Primary else TextMuted,
                    )
                },
                label = {
                    Text(
                        text = tab.title,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (selected) Primary else TextMuted,
                    )
                },
                colors = NavigationBarItemDefaults.colors(indicatorColor = PrimarySoft),
            )
        }
    }
}

private class SimpleVmFactory<T : ViewModel>(private val create: () -> T) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = create.invoke() as T
}

@Composable
fun SingleFieldEditorDialog(
    title: String,
    label: String,
    initialValue: String,
    onSave: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var value by remember { mutableStateOf(initialValue) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = { value = it },
                label = { Text(label) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
        },
        confirmButton = {
            TextButton(onClick = { onSave(value); onDismiss() }) { Text("Сохранить") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}

@Composable
fun ChangePasswordDialog(
    onSubmit: (String, String, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var oldPassword by remember { mutableStateOf("") }
    var newPassword by remember { mutableStateOf("") }
    var repeatPassword by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Изменить пароль") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = oldPassword,
                    onValueChange = { oldPassword = it },
                    label = { Text("Старый пароль") },
                    modifier = Modifier.fillMaxWidth(),
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                OutlinedTextField(
                    value = newPassword,
                    onValueChange = { newPassword = it },
                    label = { Text("Новый пароль") },
                    modifier = Modifier.fillMaxWidth(),
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
                OutlinedTextField(
                    value = repeatPassword,
                    onValueChange = { repeatPassword = it },
                    label = { Text("Повторите новый пароль") },
                    modifier = Modifier.fillMaxWidth(),
                    visualTransformation = PasswordVisualTransformation(),
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSubmit(oldPassword, newPassword, repeatPassword) }) {
                Text("Сохранить")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Отмена")
            }
        },
    )
}

@Composable
fun NotificationsDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Уведомления") },
        text = { Text("Нет новых уведомлений") },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Закрыть")
            }
        },
    )
}

@Composable
fun PassportEditorDialog(
    profile: UserProfile,
    onSave: (UserProfile) -> Unit,
    onDismiss: () -> Unit,
) {
    var firstName by remember { mutableStateOf(profile.firstName) }
    var lastName by remember { mutableStateOf(profile.lastName) }
    var middleName by remember { mutableStateOf(profile.middleName) }
    var passportIssuedBy by remember { mutableStateOf(profile.passportIssuedBy) }
    var passportIssueDate by remember { mutableStateOf(profile.passportIssueDate) }
    var passportUnitCode by remember { mutableStateOf(profile.passportUnitCode) }
    var passportSeriesNumber by remember { mutableStateOf(profile.passportSeriesNumber) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Редактор персональных данных") },
        text = {
            Column(
                modifier = Modifier
                    .imePadding()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = firstName,
                    onValueChange = { firstName = it },
                    label = { Text("Имя") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = lastName,
                    onValueChange = { lastName = it },
                    label = { Text("Фамилия") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = middleName,
                    onValueChange = { middleName = it },
                    label = { Text("Отчество") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = passportIssuedBy,
                    onValueChange = { passportIssuedBy = it },
                    label = { Text("Паспорт выдан") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = passportIssueDate,
                    onValueChange = { passportIssueDate = it },
                    label = { Text("Дата выдачи") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = passportUnitCode,
                    onValueChange = { passportUnitCode = it },
                    label = { Text("Код подразделения") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = passportSeriesNumber,
                    onValueChange = { passportSeriesNumber = it },
                    label = { Text("Серия и номер") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onSave(
                        profile.copy(
                            firstName = firstName,
                            lastName = lastName,
                            middleName = middleName,
                            passportIssuedBy = passportIssuedBy,
                            passportIssueDate = passportIssueDate,
                            passportUnitCode = passportUnitCode,
                            passportSeriesNumber = passportSeriesNumber,
                        ),
                    )
                },
            ) { Text("Сохранить") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}
@Composable
fun AiSettingsDialog(
    settings: AppSettings,
    gigaConfigured: Boolean,
    offlineModelInstalled: Boolean,
    downloadMessage: String,
    onUseGigaChatChange: (Boolean) -> Unit,
    onProfileChange: (RamProfile) -> Unit,
    onDownloadLocalModel: () -> Unit,
    onDeleteLocalModel: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u0418\u0418") },
        text = {
            Column(
                modifier = Modifier.imePadding(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c GigaChat", modifier = Modifier.weight(1f))
                    Switch(checked = settings.useGigaChat, onCheckedChange = onUseGigaChatChange)
                }

                if (settings.useGigaChat) {
                    Text(
                        text = if (gigaConfigured) {
                            "GigaChat \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d \u0432 \u043a\u043e\u0434\u0435 \u0438 \u0431\u0443\u0434\u0435\u0442 \u043e\u0442\u0432\u0435\u0447\u0430\u0442\u044c \u0432 \u0447\u0430\u0442\u0435."
                        } else {
                            "GigaChat \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d \u0432 \u0441\u0431\u043e\u0440\u043a\u0435: \u0437\u0430\u0434\u0430\u0439\u0442\u0435 GIGACHAT_API_PERS \u0432 local.properties."
                        },
                        color = if (gigaConfigured) Color(0xFF2E7D32) else TextMuted,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                Text("\u041f\u0440\u043e\u0444\u0438\u043b\u044c \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u0439 \u043c\u043e\u0434\u0435\u043b\u0438:", fontWeight = FontWeight.Bold)
                RamProfile.entries.forEach { profile ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onProfileChange(profile) },
                    ) {
                        androidx.compose.material3.RadioButton(
                            selected = settings.profile == profile,
                            onClick = { onProfileChange(profile) },
                        )
                        Text(profile.name)
                    }
                }

                if (!settings.useGigaChat) {
                    Text(
                        text = if (offlineModelInstalled) {
                            "\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f \u043c\u043e\u0434\u0435\u043b\u044c \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0430. \u041e\u0442\u0432\u0435\u0442\u044b \u043f\u043e\u0439\u0434\u0443\u0442 \u0447\u0435\u0440\u0435\u0437 GGUF."
                        } else {
                            "\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u0430\u044f \u043c\u043e\u0434\u0435\u043b\u044c \u043d\u0435 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0430. \u0421\u043a\u0430\u0447\u0430\u0439\u0442\u0435 GGUF \u0434\u043b\u044f \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0444\u0438\u043b\u044f."
                        },
                        color = if (offlineModelInstalled) Color(0xFF2E7D32) else TextMuted,
                        style = MaterialTheme.typography.bodySmall,
                    )
                    if (downloadMessage.isNotBlank()) {
                        Text(downloadMessage, style = MaterialTheme.typography.bodySmall, color = TextMuted)
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onDownloadLocalModel) {
                            Text("\u0421\u043a\u0430\u0447\u0430\u0442\u044c \u043c\u043e\u0434\u0435\u043b\u044c")
                        }
                        OutlinedButton(onClick = onDeleteLocalModel) {
                            Text("\u0423\u0434\u0430\u043b\u0438\u0442\u044c")
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("\u0417\u0430\u043a\u0440\u044b\u0442\u044c")
            }
        },
    )
}
@Composable
fun ChatHistoryDialog(
    chats: List<com.dtp.dtpassist.domain.model.ChatThread>,
    currentChatId: Long,
    onSelectChat: (Long) -> Unit,
    onCreateNewChat: () -> Unit,
    onClearAll: () -> Unit,
    onDismiss: () -> Unit,
) {
    val formatter = remember { SimpleDateFormat("dd.MM HH:mm", Locale.getDefault()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("История чатов") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onCreateNewChat, modifier = Modifier.weight(1f)) {
                        Text("Новый чат")
                    }
                    OutlinedButton(onClick = onClearAll, modifier = Modifier.weight(1f)) {
                        Text("Очистить")
                    }
                }
                HorizontalDivider()
                LazyColumn(modifier = Modifier.height(260.dp)) {
                    items(chats) { chat ->
                        val selected = chat.id == currentChatId
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onSelectChat(chat.id) }
                                .padding(vertical = 10.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = chat.title,
                                    fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                                    color = if (selected) Primary else Color.Unspecified,
                                )
                                Text(
                                    text = formatter.format(Date(chat.createdAt)),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = TextMuted,
                                )
                            }
                            if (selected) {
                                Text("Текущий", color = Primary, style = MaterialTheme.typography.labelSmall)
                            }
                        }
                        HorizontalDivider()
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } },
    )
}








