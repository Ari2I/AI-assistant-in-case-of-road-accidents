// ============================================
// ДОМ ЭЛЕМЕНТЫ
// ============================================
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const messagesContainer = document.getElementById('messagesContainer');
const typingIndicator = document.getElementById('typingIndicator');
const quickActionChips = document.querySelectorAll('.quick-action-chip');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.getElementById('sidebar');
const newChatBtn = document.getElementById('newChatBtn');
const openProfileBtn = document.getElementById('openProfileBtn');
const shareChatBtn = document.getElementById('shareChatBtn');
const attachBtn = document.getElementById('attachBtn');

// Модальные окна
const photoModal = document.getElementById('photoModal');
const profileModal = document.getElementById('profileModal');
const callModal = document.getElementById('callModal');
const modalCloses = document.querySelectorAll('.modal-close, .btn-cancel');
const photoSubmitBtn = document.getElementById('photoSubmitBtn');
const profileSaveBtn = document.getElementById('profileSaveBtn');
const modalFileInput = document.getElementById('modalFileInput');
const modalCameraInput = document.getElementById('modalCameraInput');
const photoPreviewList = document.getElementById('photoPreviewList');

// Элементы профиля
const profileNameInput = document.getElementById('profileName');
const profilePhoneInput = document.getElementById('profilePhone');
const profileEmailInput = document.getElementById('profileEmail');
const profilePolicyInput = document.getElementById('profilePolicy');

// Переключатель языка
const langSwitch = document.getElementById('langSwitch');
let currentLang = 'ru';

// Состояние чата
let currentStep = null;
let euroData = {
  date: null,
  place: null,
  carA: null,
  carB: null,
  witnesses: null,
  circumstances: null
};
let pendingPhotos = [];
let chatHistory = [];
let currentChatId = 1;

// ============================================
// ПЕРЕВОДЫ
// ============================================
const translations = {
  ru: {
    welcome: "Здравствуйте! Я ваш AI помощник по оформлению ДТП. 🚗\n\nЯ помогу вам:\n✅ Оформить европротокол по шагам\n✅ Сделать правильную фотофиксацию\n✅ Заполнить все необходимые документы\n✅ Рассчитать примерную выплату по ОСАГО\n\n👉 Выберите действие ниже или просто напишите свой вопрос",
    euro_start: "Отлично! Давайте оформим европротокол. Я буду задавать вам вопросы, а вы отвечайте. Начнём?",
    euro_question_1: "📅 **Шаг 1 из 6:** Укажите дату и время ДТП (например: 10.04.2026 15:30)",
    euro_question_2: "📍 **Шаг 2 из 6:** Где произошло ДТП? (город, улица, ориентиры)",
    euro_question_3: "🚗 **Шаг 3 из 6:** Данные вашего автомобиля (автомобиль А). Укажите: госномер и ФИО владельца через запятую",
    euro_question_4: "🚙 **Шаг 4 из 6:** Данные второго автомобиля (автомобиль Б). Укажите: госномер и ФИО владельца через запятую",
    euro_question_5: "👥 **Шаг 5 из 6:** Есть ли свидетели? Если да, укажите ФИО и контакты (если нет, напишите 'нет')",
    euro_question_6: "📝 **Шаг 6 из 6:** Кратко опишите обстоятельства ДТП (кто двигался, кто нарушил, и т.д.)",
    euro_success: "✅ **Отлично! Данные европротокола сохранены!**\n\n```\n📅 Дата: {date}\n📍 Место: {place}\n🚗 Авто А: {carA}\n🚙 Авто Б: {carB}\n👥 Свидетели: {witnesses}\n📝 Обстоятельства: {circumstances}\n```\n\n**Что делать дальше:**\n1. 📸 Сделайте фото места ДТП и повреждений\n2. 📄 Заполните бумажный бланк европротокола\n3. 📷 Сфотографируйте заполненный бланк\n4. 🏦 Отправьте всё в страховую в течение 5 дней\n\nХотите, я рассчитаю примерную выплату? Или помогу с фотофиксацией?",
    photo_guide: "📸 **Как правильно сфотографировать место ДТП:**\n\n1️⃣ **Общий план** — место ДТП с высоты, видны оба авто и дорога\n2️⃣ **Расположение** — авто относительно разметки, знаков, светофоров\n3️⃣ **Повреждения** — крупным планом, со всех ракурсов\n4️⃣ **Госномера** — обоих автомобилей\n5️⃣ **Документы** — заполненный европротокол\n\n👉 Нажмите на скрепку 📎 внизу, чтобы загрузить фото, или сделайте фото прямо сейчас.",
    payout_calc: "💰 **Расчёт примерной выплаты по ОСАГО**\n\nМаксимальная сумма по европротоколу: **100 000 ₽**\n(до 400 000 ₽ в Москве, СПб и областях)\n\n**Факторы, влияющие на выплату:**\n• Износ деталей — до 50%\n• Стоимость работ по среднерыночным ценам\n• Наличие фотофиксации\n\n📌 Для точного расчёта отправьте фото повреждений в чат — я помогу оценить.\n\nХотите узнать, как увеличить сумму выплаты?",
    deadlines: "⏰ **Сроки подачи документов в страховую**\n\n⚠️ **Важно!** Документы нужно подать в течение **5 рабочих дней** после ДТП.\n\n**Что нужно подать:**\n1. Заявление о страховом случае\n2. Заполненный европротокол\n3. Фото/видео материалы\n4. Паспорт и права\n5. Реквизиты для перевода\n\nОпоздание может стать причиной отказа в выплате!",
    emergency: "🚨 **Вызов экстренных служб**\n\nНажмите на кнопку вызова ниже, чтобы позвонить:\n\n• **112** — единый номер экстренных служб\n• **102** — полиция\n• **103** — скорая помощь\n\n⚠️ Звоните только в случае реальной необходимости!",
    photo_received: "📸 Спасибо за фото! Я сохранил {count} снимков. Они помогут при оформлении страхового случая.\n\nХотите добавить ещё фото или продолжить оформление?",
    unknown: "Я не совсем понял. Выберите действие из предложенных ниже или напишите 'помощь' для списка команд.\n\nДоступные команды:\n• европротокол / euro — начать оформление\n• фото / photo — инструкция по фотофиксации\n• выплата / payout — рассчитать выплату\n• сроки / deadline — сроки подачи\n• помощь / help — показать это сообщение"
  },
  en: {
    welcome: "Hello! I'm your AI assistant for accident reporting. 🚗\n\nI can help you:\n✅ Complete Europrotocol step by step\n✅ Take proper photos of the scene\n✅ Fill out all necessary documents\n✅ Calculate approximate insurance payout\n\n👉 Choose an action below or just type your question",
    euro_start: "Great! Let's complete the Europrotocol. I'll ask you questions, just answer them. Shall we start?",
    euro_question_1: "📅 **Step 1 of 6:** Enter the date and time of the accident (e.g., 04/10/2026 15:30)",
    euro_question_2: "📍 **Step 2 of 6:** Where did the accident happen? (city, street, landmarks)",
    euro_question_3: "🚗 **Step 3 of 6:** Your vehicle details (Vehicle A): license plate and owner's full name",
    euro_question_4: "🚙 **Step 4 of 6:** Other vehicle details (Vehicle B): license plate and owner's full name",
    euro_question_5: "👥 **Step 5 of 6:** Are there witnesses? If yes, provide names and contacts (if no, write 'none')",
    euro_question_6: "📝 **Step 6 of 6:** Briefly describe the circumstances of the accident",
    euro_success: "✅ **Great! Europrotocol data saved!**\n\n```\n📅 Date: {date}\n📍 Place: {place}\n🚗 Vehicle A: {carA}\n🚙 Vehicle B: {carB}\n👥 Witnesses: {witnesses}\n📝 Circumstances: {circumstances}\n```\n\n**Next steps:**\n1. 📸 Take photos of the scene and damages\n2. 📄 Fill out the paper Europrotocol form\n3. 📷 Take photos of the completed form\n4. 🏦 Submit everything to insurance within 5 days\n\nWould you like me to calculate an approximate payout? Or help with photos?",
    photo_guide: "📸 **How to properly photograph the accident scene:**\n\n1️⃣ **Overall view** — shows both cars and the road\n2️⃣ **Position** — cars relative to markings, signs, traffic lights\n3️⃣ **Damages** — close-ups from all angles\n4️⃣ **License plates** — of both vehicles\n5️⃣ **Documents** — completed Europrotocol form\n\n👉 Click the paperclip 📎 below to upload photos, or take a photo right now.",
    payout_calc: "💰 **Approximate insurance payout calculation**\n\nMaximum amount under Europrotocol: **$1,200 USD**\n\n**Factors affecting payout:**\n• Parts depreciation — up to 50%\n• Labor costs at market rates\n• Quality of photo documentation\n\n📌 For accurate calculation, send photos of damages to chat — I'll help assess.\n\nWant to know how to increase your payout?",
    deadlines: "⏰ **Deadlines for submitting documents to insurance**\n\n⚠️ **Important!** Documents must be submitted within **5 business days** after the accident.\n\n**What to submit:**\n1. Insurance claim application\n2. Completed Europrotocol\n3. Photo/video materials\n4. Passport and driver's license\n5. Bank details for transfer\n\nMissing the deadline may result in refusal of payment!",
    emergency: "🚨 **Emergency services call**\n\nClick the call button below to dial:\n\n• **112** — unified emergency number\n• **102** — police\n• **103** — ambulance\n\n⚠️ Only call if truly necessary!",
    photo_received: "📸 Thank you for the photos! I saved {count} images. They will help with your insurance claim.\n\nWould you like to add more photos or continue with the process?",
    unknown: "I didn't quite understand. Choose an action from the options below or type 'help' for available commands.\n\nAvailable commands:\n• europrotocol / euro — start Europrotocol\n• photo — photo instructions\n• payout — calculate payout\n• deadline — submission deadlines\n• help — show this message"
  }
};

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================

function t(key, replacements = {}) {
  let text = translations[currentLang][key] || translations.ru[key] || key;
  for (const [k, v] of Object.entries(replacements)) {
    text = text.replace(`{${k}}`, v);
  }
  return text;
}

function addMessage(text, type = 'assistant') {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message--${type}`;
  
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = type === 'assistant' ? '🤖' : '👤';
  
  const content = document.createElement('div');
  content.className = 'message-content';
  
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  
  // Обработка markdown-like форматирования
  let formattedText = text;
  formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formattedText = formattedText.replace(/`(.*?)`/g, '<code>$1</code>');
  formattedText = formattedText.replace(/\n/g, '<br>');
  
  bubble.innerHTML = formattedText;
  content.appendChild(bubble);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);
  
  messagesContainer.appendChild(messageDiv);
  scrollToBottom();
  
  // Сохраняем в историю
  chatHistory.push({ text, type, timestamp: new Date() });
}

function scrollToBottom() {
  const chatArea = document.getElementById('chatMessagesArea');
  chatArea.scrollTop = chatArea.scrollHeight;
}

async function showTyping(duration = 1500) {
  typingIndicator.style.display = 'block';
  scrollToBottom();
  await new Promise(resolve => setTimeout(resolve, duration));
  typingIndicator.style.display = 'none';
}

async function simulateAssistantResponse(responseText) {
  await showTyping(1000);
  addMessage(responseText, 'assistant');
}

function processUserMessage(message) {
  const lowerMsg = message.toLowerCase().trim();
  
  // Обработка пошагового сбора данных
  if (currentStep) {
    processEuroStep(message);
    return;
  }
  
  // Команды
  if (lowerMsg === 'помощь' || lowerMsg === 'help') {
    simulateAssistantResponse(t('unknown'));
    return;
  }
  
  if (lowerMsg.includes('европротокол') || lowerMsg.includes('euro') || lowerMsg === 'начать' || lowerMsg === 'start') {
    startEuroprotocol();
    return;
  }
  
  if (lowerMsg.includes('фото') || lowerMsg.includes('photo')) {
    simulateAssistantResponse(t('photo_guide'));
    return;
  }
  
  if (lowerMsg.includes('выплат') || lowerMsg.includes('payout') || lowerMsg.includes('расчёт')) {
    simulateAssistantResponse(t('payout_calc'));
    return;
  }
  
  if (lowerMsg.includes('срок') || lowerMsg.includes('deadline') || lowerMsg.includes('подач')) {
    simulateAssistantResponse(t('deadlines'));
    return;
  }
  
  if (lowerMsg.includes('вызов') || lowerMsg.includes('call') || lowerMsg.includes('112')) {
    simulateAssistantResponse(t('emergency'));
    setTimeout(() => openModal(callModal), 500);
    return;
  }
  
  // Обычный ответ
  simulateAssistantResponse(t('unknown'));
}

function startEuroprotocol() {
  currentStep = 1;
  euroData = {
    date: null,
    place: null,
    carA: null,
    carB: null,
    witnesses: null,
    circumstances: null
  };
  simulateAssistantResponse(t('euro_start'));
  setTimeout(() => {
    simulateAssistantResponse(t('euro_question_1'));
  }, 1000);
}

function processEuroStep(message) {
  switch (currentStep) {
    case 1:
      euroData.date = message;
      currentStep = 2;
      simulateAssistantResponse(t('euro_question_2'));
      break;
    case 2:
      euroData.place = message;
      currentStep = 3;
      simulateAssistantResponse(t('euro_question_3'));
      break;
    case 3:
      euroData.carA = message;
      currentStep = 4;
      simulateAssistantResponse(t('euro_question_4'));
      break;
    case 4:
      euroData.carB = message;
      currentStep = 5;
      simulateAssistantResponse(t('euro_question_5'));
      break;
    case 5:
      euroData.witnesses = message;
      currentStep = 6;
      simulateAssistantResponse(t('euro_question_6'));
      break;
    case 6:
      euroData.circumstances = message;
      currentStep = null;
      
      const successMsg = t('euro_success', {
        date: euroData.date,
        place: euroData.place,
        carA: euroData.carA,
        carB: euroData.carB,
        witnesses: euroData.witnesses,
        circumstances: euroData.circumstances
      });
      simulateAssistantResponse(successMsg);
      
      // Сохраняем в localStorage
      const reports = JSON.parse(localStorage.getItem('euroReports') || '[]');
      reports.push({ ...euroData, timestamp: new Date().toISOString() });
      localStorage.setItem('euroReports', JSON.stringify(reports));
      break;
  }
}

// ============================================
// МОДАЛЬНЫЕ ОКНА
// ============================================

function openModal(modal) {
  if (modal) modal.classList.add('modal--visible');
}

function closeModal(modal) {
  if (modal) modal.classList.remove('modal--visible');
}

function closeAllModals() {
  document.querySelectorAll('.modal').forEach(modal => {
    modal.classList.remove('modal--visible');
  });
}

// Фото модалка
function handlePhotoFiles(files) {
  pendingPhotos = [];
  photoPreviewList.innerHTML = '';
  
  Array.from(files).forEach(file => {
    if (file.type.startsWith('image/')) {
      pendingPhotos.push(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = document.createElement('img');
        img.src = e.target.result;
        img.className = 'photo-preview';
        photoPreviewList.appendChild(img);
      };
      reader.readAsDataURL(file);
    }
  });
}

if (modalFileInput) {
  modalFileInput.addEventListener('change', (e) => {
    handlePhotoFiles(e.target.files);
  });
}

if (modalCameraInput) {
  modalCameraInput.addEventListener('change', (e) => {
    handlePhotoFiles(e.target.files);
  });
}

if (photoSubmitBtn) {
  photoSubmitBtn.addEventListener('click', async () => {
    if (pendingPhotos.length > 0) {
      closeModal(photoModal);
      await showTyping(1200);
      addMessage(t('photo_received', { count: pendingPhotos.length }), 'assistant');
      pendingPhotos = [];
    } else {
      alert('Пожалуйста, выберите фото');
    }
  });
}

// Профиль
function loadProfile() {
  const profile = JSON.parse(localStorage.getItem('userProfile') || '{}');
  if (profileNameInput) profileNameInput.value = profile.name || '';
  if (profilePhoneInput) profilePhoneInput.value = profile.phone || '';
  if (profileEmailInput) profileEmailInput.value = profile.email || '';
  if (profilePolicyInput) profilePolicyInput.value = profile.policy || '';
}

function saveProfile() {
  const profile = {
    name: profileNameInput?.value || '',
    phone: profilePhoneInput?.value || '',
    email: profileEmailInput?.value || '',
    policy: profilePolicyInput?.value || ''
  };
  localStorage.setItem('userProfile', JSON.stringify(profile));
  closeModal(profileModal);
  addMessage('👤 Профиль сохранён! Теперь я могу использовать ваши данные при оформлении.', 'assistant');
}

// Экстренный вызов
function setupEmergencyCalls() {
  const emergencyCards = document.querySelectorAll('.emergency-card');
  emergencyCards.forEach(card => {
    card.addEventListener('click', () => {
      const number = card.dataset.number;
      if (number) {
        window.location.href = `tel:${number}`;
      }
    });
  });
}

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ
// ============================================

// Отправка сообщения
function sendMessage() {
  const message = messageInput.value.trim();
  if (!message) return;
  
  addMessage(message, 'user');
  messageInput.value = '';
  
  processUserMessage(message);
}

if (sendBtn) {
  sendBtn.addEventListener('click', sendMessage);
}

if (messageInput) {
  messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });
}

// Быстрые действия
quickActionChips.forEach(chip => {
  chip.addEventListener('click', () => {
    const action = chip.dataset.action;
    switch (action) {
      case 'euro':
        startEuroprotocol();
        break;
      case 'photo':
        simulateAssistantResponse(t('photo_guide'));
        setTimeout(() => openModal(photoModal), 1000);
        break;
      case 'payout':
        simulateAssistantResponse(t('payout_calc'));
        break;
      case 'deadline':
        simulateAssistantResponse(t('deadlines'));
        break;
      case 'call':
        simulateAssistantResponse(t('emergency'));
        setTimeout(() => openModal(callModal), 500);
        break;
    }
  });
});

// Прикрепление файлов
if (attachBtn) {
  attachBtn.addEventListener('click', () => {
    openModal(photoModal);
  });
}

// Мобильное меню
if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener('click', () => {
    sidebar.classList.toggle('sidebar--open');
  });
}

// Новый чат
if (newChatBtn) {
  newChatBtn.addEventListener('click', () => {
    currentStep = null;
    euroData = {};
    messagesContainer.innerHTML = '';
    addMessage(t('welcome'), 'assistant');
    currentChatId++;
  });
}

// Профиль
if (openProfileBtn) {
  openProfileBtn.addEventListener('click', () => {
    loadProfile();
    openModal(profileModal);
  });
}

if (profileSaveBtn) {
  profileSaveBtn.addEventListener('click', saveProfile);
}

// Поделиться чатом
if (shareChatBtn) {
  shareChatBtn.addEventListener('click', async () => {
    const chatText = chatHistory.map(m => `${m.type === 'user' ? '👤' : '🤖'}: ${m.text}`).join('\n\n');
    try {
      await navigator.clipboard.writeText(chatText);
      addMessage('📋 История чата скопирована в буфер обмена', 'assistant');
    } catch (err) {
      alert('Не удалось скопировать');
    }
  });
}

// Закрытие модалок
modalCloses.forEach(btn => {
  btn.addEventListener('click', closeAllModals);
});

// Клик вне модалки
document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeAllModals();
  });
});

// Переключение языка
if (langSwitch) {
  langSwitch.addEventListener('click', (e) => {
    const btn = e.target.closest('.lang-btn');
    if (!btn) return;
    const newLang = btn.dataset.lang === 'ru' ? 'ru' : 'en';
    if (newLang === currentLang) return;
    currentLang = newLang;
    
    langSwitch.querySelectorAll('.lang-btn').forEach(b => {
      b.classList.toggle('lang-btn--active', b.dataset.lang === currentLang);
    });
    
    // Обновляем последнее сообщение ассистента
    addMessage(t('welcome'), 'assistant');
  });
}

// Обработка Esc
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeAllModals();
    if (sidebar.classList.contains('sidebar--open')) {
      sidebar.classList.remove('sidebar--open');
    }
  }
});

// Настройка экстренных вызовов
setupEmergencyCalls();

// Инициализация
addMessage(t('welcome'), 'assistant');
loadProfile();

// Сохранение данных перед закрытием
window.addEventListener('beforeunload', () => {
  if (euroData.date || euroData.place) {
    localStorage.setItem('draftEuroData', JSON.stringify(euroData));
  }
});

console.log('✅ Чат ассистент готов к работе!');