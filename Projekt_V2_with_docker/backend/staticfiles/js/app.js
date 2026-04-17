// ----------------------------------------------
// DOM
// ----------------------------------------------

const topProgressBar = document.getElementById("topProgressBar");
const stepLabel = document.getElementById("stepLabel");
const wizardSteps = document.querySelectorAll(".wizard-step");

const optionCards = document.querySelectorAll(".option-card");
const wizardNextBtnStep1 = document.getElementById("wizardNextBtnStep1");

const fileInput = document.getElementById("fileInput");
const cameraInput = document.getElementById("cameraInput");
const uploadList = document.getElementById("uploadList");
const extraProtoBtn = document.getElementById("protoPhotoBtn");

const detectLocationBtn = document.getElementById("detectLocationBtn");
const euroPlaceInput = document.getElementById("euroPlace");
const euroForm = document.getElementById("euroForm");
const euroSaveBtn = document.getElementById("euroSaveBtn");

const wizardFinishBtn = document.getElementById("wizardFinishBtn");
const call112Btn = document.getElementById("call112Btn");

const profilePanel = document.getElementById("profilePanel");
const openProfileBtn = document.getElementById("openProfileBtn");
const closeProfileBtn = document.getElementById("closeProfileBtn");
const profileSaveBtn = document.getElementById("profileSaveBtn");
const profileForm = document.getElementById("profileForm");

const chatWindow = document.getElementById("chatWindow");
const chatToggleBtn = document.getElementById("chatToggleBtn");
const chatCloseBtn = document.getElementById("chatCloseBtn");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");

const langSwitch = document.getElementById("langSwitch");
let currentLang = "ru";

// Навигация по вкладкам
const navButtons = document.querySelectorAll(".main-nav-btn");
const screenWizard = document.getElementById("screen-wizard");
const screenInsurance = document.getElementById("screen-insurance");

// ----------------------------------------------
// I18N (RU / EN)
// ----------------------------------------------

const translations = {
  ru: {
    "app.title": "Ассистент ДТП",
    "app.subtitle": "Шаг за шагом через оформление",

    "wizard.label": "Оформление ДТП",
    "nav.wizard": "Пошагово",
    "nav.insurance": "Страховая",

    "btn.back": "Назад",
    "btn.next": "Далее",

    "step1.title": "Шаг 1. Тип происшествия",
    "step1.subtitle": "Укажите, что произошло. Для европротокола будут доступны все шаги.",
    "step1.serious.title": "Серьёзное ДТП",
    "step1.serious.desc": "Есть пострадавшие, крупный ущерб или спорная ситуация.",
    "step1.serious.tag": "Обычно требуется вызов ГИБДД",
    "step1.serious.diffTitle": "Чем отличается от европротокола",
    "step1.serious.diffText":
      "Применяется, когда есть пострадавшие, высокий ущерб, много участников или водители не согласны между собой.",
    "step1.euro.title": "Европротокол",
    "step1.euro.desc": "Нет пострадавших, только ущерб автомобилям, участники согласны.",
    "step1.euro.tag": "Можно оформить без вызова ГИБДД",
    "step1.euro.diffTitle": "Чем отличается от серьёзного ДТП",
    "step1.euro.diffText":
      "Используется при двух авто с ОСАГО, без вреда здоровью и при согласии водителей, когда ущерб не превышает лимит по европротоколу.",

    "step2.title": "Шаг 2. Обозначьте место ДТП",
    "step2.subtitle": "Выставьте аварийный знак и включите аварийную сигнализацию.",

    "step3.title": "Шаг 3. При необходимости вызовите 112",
    "step3.subtitle": "Если есть пострадавшие или угроза, незамедлительно позвоните по номеру 112.",
    "step3.call112": "Позвонить 112",

    "step4.title": "Шаг 4. Проверьте полисы ОСАГО",
    "step4.subtitle": "Убедитесь, что у обоих водителей есть действующие полисы ОСАГО.",
    "step4.checkOsago": "проверить ОСАГО",

    "step5.title": "Шаг 5. Сделайте и приложите фотографии",
    "step5.subtitle": "Сфотографируйте место ДТП, повреждения и номера машин.",
    "step5.attachTitle": "Прикрепить фото с места ДТП:",
    "step5.cameraLabel": "Или сделайте фото с камеры:",

    "step6.title": "Шаг 6. Заполните форму европротокола",
    "step6.subtitle": "Укажите основные данные о ДТП и участниках.",

    "step7.title": "Шаг 7. Зафиксируйте заполненный европротокол",
    "step7.subtitle":
      "Прикрепите фото заполненных пунктов европротокола для надёжности.",
    "step7.attach": "прикрепите фото заполненых пунктов европротокола",

    "step8.title": "Шаг 8. Подписи обоих водителей",
    "step8.subtitle": "Перепроверьте всё и подпишите документ с обеих сторон.",
    "step8.helper":
      "Перепроверьте все данные, убедитесь, что обе стороны согласны и подписи стоят в нужных местах.",

    "step9.title": "Шаг 9. Передайте документы в страховую",
    "step9.subtitle":
      "Передайте оформленный европротокол и материалы в страховую компанию в установленные сроки.",
    "step9.finish": "Завершить",

    "euro.dateLabel": "Дата и время ДТП",
    "euro.placeLabel": "Место ДТП",
    "euro.placePlaceholder": "Город, улица, ориентиры",
    "euro.detect": "Определить",
    "euro.detectHint": "Кнопка попробует определить адрес по вашей геолокации.",
    "euro.witnessesLabel": "Свидетели (ФИО, контакты)",
    "euro.witnessesPlaceholder": "Если свидетелей нет, можно написать «нет»",
    "euro.carA.title": "Данные автомобиля A",
    "euro.carB.title": "Данные автомобиля B",
    "euro.car.ownerLabel": "Страхователь / владелец",
    "euro.car.ownerPlaceholder": "ФИО",
    "euro.car.plateLabel": "Госномер",
    "euro.car.platePlaceholder": "А000АА000",
    "euro.circLabel": "Краткое описание обстоятельств ДТП",
    "euro.circPlaceholder":
      "Например: автомобиль A двигался прямо, автомобиль B поворачивал налево...",

    "insurance.title": "Страховая",
    "insurance.subtitle":
      "Здесь будет чат с ботом, который сможет рассчитать максимальную сумму выплаты от страховой.",

    "profile.title": "Профиль",
    "profile.close": "Закрыть",
    "profile.nameLabel": "Имя",
    "profile.namePlaceholder": "Иван Иванов",
    "profile.emailLabel": "E‑mail",
    "profile.emailPlaceholder": "you@example.com",
    "profile.phoneLabel": "Телефон",
    "profile.phonePlaceholder": "+7 900 000‑00‑00",
    "profile.passwordTitle": "Смена пароля",
    "profile.newPassword": "Новый пароль",
    "profile.repeatPassword": "Повторите пароль",
    "profile.save": "Сохранить",

    "chat.title": "Вопрос ассистенту",
    "chat.welcome":
      "Я — цифровой ассистент. Спросите, что вас волнует по оформлению ДТП.",
    "chat.placeholder": "Напишите вопрос..."
  },
  en: {
    "app.title": "Accident Assistant",
    "app.subtitle": "Step-by-step crash guidance",

    "wizard.label": "Accident workflow",
    "nav.wizard": "Wizard",
    "nav.insurance": "Insurance",

    "btn.back": "Back",
    "btn.next": "Next",

    "step1.title": "Step 1. Type of incident",
    "step1.subtitle":
      "Specify what happened. For the Europrotocol all steps will be available.",
    "step1.serious.title": "Serious accident",
    "step1.serious.desc":
      "There are injured people, major damage or a disputed situation.",
    "step1.serious.tag": "Usually requires calling the police",
    "step1.serious.diffTitle": "How it differs from Europrotocol",
    "step1.serious.diffText":
      "Used when there are injured, high damage, many participants or drivers disagree.",
    "step1.euro.title": "Europrotocol",
    "step1.euro.desc":
      "No injured, only vehicle damage, drivers agree on what happened.",
    "step1.euro.tag": "Can be completed without calling the police",
    "step1.euro.diffTitle": "How it differs from a serious accident",
    "step1.euro.diffText":
      "Used for two vehicles with insurance, no harm to health and agreed circumstances, when damage is below the legal limit.",

    "step2.title": "Step 2. Mark the accident",
    "step2.subtitle":
      "Place the warning triangle and turn on hazard lights.",

    "step3.title": "Step 3. Call 112 if needed",
    "step3.subtitle":
      "If there are injured people or danger, call 112 immediately.",
    "step3.call112": "Call 112",

    "step4.title": "Step 4. Check insurance policies",
    "step4.subtitle":
      "Make sure both drivers have valid MTPL/insurance policies.",
    "step4.checkOsago": "check insurance",

    "step5.title": "Step 5. Take and attach photos",
    "step5.subtitle":
      "Take photos of the scene, damages and license plates.",
    "step5.attachTitle": "Attach photos from device:",
    "step5.cameraLabel": "Or take a photo with camera:",

    "step6.title": "Step 6. Fill in Europrotocol form",
    "step6.subtitle": "Provide main data about the accident and participants.",

    "step7.title": "Step 7. Capture filled Europrotocol",
    "step7.subtitle":
      "Attach photos of the filled Europrotocol fields for reliability.",
    "step7.attach": "attach photos of the filled Europrotocol",

    "step8.title": "Step 8. Driver signatures",
    "step8.subtitle": "Double‑check everything and have both drivers sign.",
    "step8.helper":
      "Check all data, make sure both parties agree and signatures are in place.",

    "step9.title": "Step 9. Send to insurance",
    "step9.subtitle":
      "Submit the completed Europrotocol and materials to the insurance company in time.",
    "step9.finish": "Finish",

    "euro.dateLabel": "Date and time of accident",
    "euro.placeLabel": "Place of accident",
    "euro.placePlaceholder": "City, street, landmarks",
    "euro.detect": "Detect",
    "euro.detectHint":
      "The button will try to detect the address using your geolocation.",
    "euro.witnessesLabel": "Witnesses (name, contacts)",
    "euro.witnessesPlaceholder": "If there are no witnesses, you can write “none”",
    "euro.carA.title": "Vehicle A details",
    "euro.carB.title": "Vehicle B details",
    "euro.car.ownerLabel": "Policyholder / owner",
    "euro.car.ownerPlaceholder": "Full name",
    "euro.car.plateLabel": "License plate",
    "euro.car.platePlaceholder": "A000AA000",
    "euro.circLabel": "Short description of circumstances",
    "euro.circPlaceholder":
      "Example: vehicle A was going straight, vehicle B was turning left...",

    "insurance.title": "Insurance",
    "insurance.subtitle":
      "Here will be a chat with a bot that can calculate the maximum payout from the insurance company.",

    "profile.title": "Profile",
    "profile.close": "Close",
    "profile.nameLabel": "Name",
    "profile.namePlaceholder": "John Smith",
    "profile.emailLabel": "E‑mail",
    "profile.emailPlaceholder": "you@example.com",
    "profile.phoneLabel": "Phone",
    "profile.phonePlaceholder": "+1 555 000‑0000",
    "profile.passwordTitle": "Change password",
    "profile.newPassword": "New password",
    "profile.repeatPassword": "Repeat password",
    "profile.save": "Save",

    "chat.title": "Ask assistant",
    "chat.welcome":
      "I am a digital assistant. Ask anything about handling an accident.",
    "chat.placeholder": "Type your question..."
  }
};

function applyTranslations(lang) {
  const dict = translations[lang] || translations.ru;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) el.textContent = dict[key];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) el.placeholder = dict[key];
  });
}

// начальная локаль
applyTranslations(currentLang);

// переключатель языка
if (langSwitch) {
  langSwitch.addEventListener("click", (e) => {
    const btn = e.target.closest(".lang-btn");
    if (!btn) return;
    const newLang = btn.dataset.lang;
    if (newLang === currentLang) return;
    currentLang = newLang;

    langSwitch.querySelectorAll(".lang-btn").forEach((b) => {
      b.classList.toggle("lang-btn--active", b.dataset.lang === currentLang);
    });

    applyTranslations(currentLang);
  });
}

// ----------------------------------------------
// Навигация по вкладкам
// ----------------------------------------------

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const screenName = btn.dataset.screen;
    navButtons.forEach((b) => b.classList.remove("main-nav-btn--active"));
    btn.classList.add("main-nav-btn--active");

    screenWizard.classList.toggle("screen--active", screenName === "wizard");
    screenInsurance.classList.toggle("screen--active", screenName === "insurance");
  });
});

// ----------------------------------------------
// Шаги + анимация слева/справа
// ----------------------------------------------

let currentStep = 1;
const totalSteps = 9;

function showStep(nextStep, direction = "forward") {
  const prevStep = currentStep;
  if (nextStep === prevStep) return;

  const prevEl = Array.from(wizardSteps).find(
    (s) => Number(s.dataset.step) === prevStep
  );
  const nextEl = Array.from(wizardSteps).find(
    (s) => Number(s.dataset.step) === nextStep
  );
  if (!nextEl) return;

  // Удаляем все классы анимации
  wizardSteps.forEach((s) => {
    s.classList.remove(
      "wizard-step--active",
      "wizard-step--enter-from-right",
      "wizard-step--enter-from-left",
      "wizard-step--exit-to-left",
      "wizard-step--exit-to-right"
    );
  });

  if (prevEl) {
    if (direction === "forward") {
      prevEl.classList.add("wizard-step--exit-to-left");
    } else {
      prevEl.classList.add("wizard-step--exit-to-right");
    }
  }

  if (direction === "forward") {
    nextEl.classList.add("wizard-step--enter-from-right");
  } else {
    nextEl.classList.add("wizard-step--enter-from-left");
  }

  // Включаем новый шаг
  nextEl.classList.add("wizard-step--active");

  currentStep = nextStep;
  const percent = (currentStep / totalSteps) * 100;
  topProgressBar.style.width = percent + "%";
  stepLabel.textContent =
    currentLang === "en"
      ? `Step ${currentStep} of ${totalSteps}`
      : `Шаг ${currentStep} из ${totalSteps}`;
}

showStep(currentStep);

// ----------------------------------------------
// Выбор типа ДТП
// ----------------------------------------------

let selectedAccidentType = null;

optionCards.forEach((card) => {
  card.addEventListener("click", () => {
    optionCards.forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");

    const radio = card.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;

    selectedAccidentType = card.dataset.type;
    if (wizardNextBtnStep1) wizardNextBtnStep1.disabled = false;
  });
});

// Кнопки Далее/Назад

document.addEventListener("click", (e) => {
  const nextBtn = e.target.closest(".wizard-next");
  const backBtn = e.target.closest(".wizard-back");

  if (nextBtn) {
    if (currentStep === 1) {
      if (selectedAccidentType !== "euro") {
        alert(
          currentLang === "en"
            ? "Currently only the Europrotocol flow is implemented. Choose “Europrotocol” to continue."
            : "Сейчас настроен поток только для европротокола. Выберите «Европротокол», чтобы продолжить."
        );
        return;
      }
      console.log("Step 1 done, type:", selectedAccidentType);
      if (chatWindow && !chatWindow.classList.contains("chat-window--open")) {
        chatWindow.classList.add("chat-window--open");
      }
    }

    if (currentStep < totalSteps) {
      showStep(currentStep + 1, "forward");
    }
    return;
  }

  if (backBtn) {
    if (currentStep > 1) {
      showStep(currentStep - 1, "back");
    }
    return;
  }
});

// ----------------------------------------------
// Загрузка файлов (шаг 5)
// ----------------------------------------------

function handleFiles(files) {
  if (!uploadList) return;
  uploadList.innerHTML = "";
  files.forEach((file) => {
    const li = document.createElement("li");
    li.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
    uploadList.appendChild(li);
  });
  // TODO BACKEND: отправка FormData
}

if (fileInput) {
  fileInput.addEventListener("change", () => {
    const files = Array.from(fileInput.files || []);
    handleFiles(files);
  });
}

if (cameraInput) {
  cameraInput.addEventListener("change", () => {
    const files = Array.from(cameraInput.files || []);
    handleFiles(files);
  });
}

if (extraProtoBtn) {
  extraProtoBtn.addEventListener("click", () => {
    console.log("Attach Europrotocol photos (step 7)");
  });
}

// ----------------------------------------------
// Геолокация + Яндекс (шаг 6)
// ----------------------------------------------

if (detectLocationBtn && euroPlaceInput) {
  detectLocationBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      alert(
        currentLang === "en"
          ? "Geolocation is not supported."
          : "Геолокация не поддерживается этим устройством."
      );
      return;
    }

    detectLocationBtn.disabled = true;
    detectLocationBtn.textContent =
      currentLang === "en" ? "Detecting..." : "Определяем...";

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        console.log("Coords:", latitude, longitude);

        fetch(`/api/geocode/yandex?lat=${latitude}&lon=${longitude}`)
          .then((res) => {
            if (!res.ok) throw new Error("Geocode error");
            return res.json();
          })
          .then((data) => {
            if (data && data.address) {
              euroPlaceInput.value = data.address;
            } else {
              euroPlaceInput.value = `Lat: ${latitude.toFixed(
                5
              )}, Lon: ${longitude.toFixed(5)}`;
            }
          })
          .catch((err) => {
            console.error(err);
            alert(
              currentLang === "en"
                ? "Could not detect address. Enter it manually."
                : "Не удалось определить адрес. Введите его вручную."
            );
          })
          .finally(() => {
            detectLocationBtn.disabled = false;
            detectLocationBtn.textContent =
              currentLang === "en" ? "Detect" : "Определить";
          });
      },
      (err) => {
        console.error(err);
        alert(
          currentLang === "en"
            ? "Could not get location. Allow access to location."
            : "Не удалось получить геопозицию. Разрешите доступ к местоположению."
        );
        detectLocationBtn.disabled = false;
        detectLocationBtn.textContent =
          currentLang === "en" ? "Detect" : "Определить";
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  });
}

if (euroSaveBtn && euroForm) {
  euroSaveBtn.addEventListener("click", () => {
    const formData = new FormData(euroForm);
    const payload = Object.fromEntries(formData.entries());
    console.log("Europrotocol data:", payload);
    // TODO BACKEND: POST /api/accident/europrotocol
  });
}

// ----------------------------------------------
// Вызов 112 (шаг 3)
// ----------------------------------------------

if (call112Btn) {
  call112Btn.addEventListener("click", () => {
    window.location.href = "tel:112";
  });
}

// ----------------------------------------------
// Профиль
// ----------------------------------------------

if (openProfileBtn && profilePanel) {
  openProfileBtn.addEventListener("click", () => {
    profilePanel.classList.add("profile-panel--open");
    profilePanel.setAttribute("aria-hidden", "false");
    // TODO BACKEND: GET /api/profile
  });
}

if (closeProfileBtn && profilePanel) {
  closeProfileBtn.addEventListener("click", () => {
    profilePanel.classList.remove("profile-panel--open");
    profilePanel.setAttribute("aria-hidden", "true");
  });
}

if (profileSaveBtn && profileForm) {
  profileSaveBtn.addEventListener("click", () => {
    const formData = new FormData(profileForm);
    const payload = Object.fromEntries(formData.entries());
    if (payload.password || payload.password_repeat) {
      if (payload.password !== payload.password_repeat) {
        alert(
          currentLang === "en" ? "Passwords do not match." : "Пароли не совпадают."
        );
        return;
      }
    }
    console.log("Save profile:", payload);
    // TODO BACKEND: PUT /api/profile
  });
}

// ----------------------------------------------
// Чат‑виджет
// ----------------------------------------------

// Хранилище истории чата
let chatHistory = [];

function appendChatMessage(text, type = "user") {
  const div = document.createElement("div");
  div.className = "chat-message";
  if (type === "system") div.classList.add("chat-message--system");
  if (type === "user") div.classList.add("chat-message--user");
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
  const div = document.createElement("div");
  div.className = "chat-message chat-message--system chat-typing";
  div.id = "typingIndicator";
  div.textContent = currentLang === "en" ? "Printing..." : "Печатаю...";
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  const indicator = document.getElementById("typingIndicator");
  if (indicator) indicator.remove();
}

async function sendToAssistant(message) {
  try {
    const response = await fetch("/ai/api/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: message,
        history: chatHistory,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    if (data.error) {
      return data.error;
    }

    // Обновляем историю
    chatHistory = data.history || [];
    
    return data.response;
  } catch (error) {
    console.error("Chat API error:", error);
    return (
      currentLang === "en"
        ? "Connection error. Please try again later."
        : "Ошибка подключения. Попробуйте позже."
    );
  }
}

if (chatToggleBtn && chatWindow) {
  chatToggleBtn.addEventListener("click", () => {
    chatWindow.classList.toggle("chat-window--open");
  });
}

if (chatCloseBtn && chatWindow) {
  chatCloseBtn.addEventListener("click", () => {
    chatWindow.classList.remove("chat-window--open");
  });
}

if (chatSendBtn && chatInput) {
  chatSendBtn.addEventListener("click", async () => {
    const text = chatInput.value.trim();
    if (!text) return;
    
    appendChatMessage(text, "user");
    chatInput.value = "";
    showTypingIndicator();

    const response = await sendToAssistant(text);
    
    removeTypingIndicator();
    appendChatMessage(response, "system");
  });
}

// Отправка по Enter
if (chatInput) {
  chatInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      chatSendBtn.click();
    }
  });
}

// ----------------------------------------------
// Завершение мастера (шаг 9)
// ----------------------------------------------

if (wizardFinishBtn) {
  wizardFinishBtn.addEventListener("click", () => {
    console.log("Wizard finished");
    alert(
      currentLang === "en"
        ? "Europrotocol data collected. Submit documents to the insurance company."
        : "Данные по европротоколу собраны. Передайте документы в страховую."
    );
  });
}

// Модалка авторизации
const authModal = document.getElementById('authModal');
const loginBtn = document.getElementById('loginBtn');
const signupBtn = document.getElementById('signupBtn');
const authClose = document.getElementById('authClose');
const authTitle = document.getElementById('authTitle');
const authSubmit = document.getElementById('authSubmit');
const toggleMode = document.getElementById('toggleMode');
const repeatField = document.getElementById('repeatField');
const legalText = document.getElementById('legalText');

let mode = 'login';

function openAuth(m) {
  mode = m;
  updateAuthUI();
  authModal.classList.add('visible');
}

function closeAuth() {
  authModal.classList.remove('visible');
  // Сброс полей
  document.getElementById('email').value = '';
  document.getElementById('password').value = '';
  document.getElementById('password2').value = '';
}

function updateAuthUI() {
  if (mode === 'login') {
    authTitle.textContent = 'Вход';
    authSubmit.textContent = 'Войти';
    toggleMode.textContent = 'Нет аккаунта? Регистрация';
    repeatField.style.display = 'none';
    legalText.textContent = 'Используйте e‑mail и пароль, указанные при регистрации.';
  } else {
    authTitle.textContent = 'Регистрация';
    authSubmit.textContent = 'Создать аккаунт';
    toggleMode.textContent = 'Уже есть аккаунт? Войти';
    repeatField.style.display = 'flex';
    legalText.textContent = 'Создавая аккаунт, вы принимаете условия сервиса и даёте согласие на обработку персональных данных.';
  }
}

loginBtn.addEventListener('click', () => openAuth('login'));
signupBtn.addEventListener('click', () => openAuth('signup'));
authClose.addEventListener('click', closeAuth);

toggleMode.addEventListener('click', () => {
  mode = mode === 'login' ? 'signup' : 'login';
  updateAuthUI();
});

authModal.addEventListener('click', (e) => {
  if (e.target === authModal) closeAuth();
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && authModal.classList.contains('visible')) {
    closeAuth();
  }
});

authSubmit.addEventListener('click', (e) => {
  e.preventDefault();
  console.log('AUTH SUBMIT, mode:', mode, {
    email: document.getElementById('email').value,
    password: document.getElementById('password').value,
    password2: document.getElementById('password2').value
  });
});
