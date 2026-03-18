// ----------------------------------------------
// Ссылки на DOM
// ----------------------------------------------

// Навигация по экранам
const navButtons = document.querySelectorAll(".main-nav-btn");
const screens = {
  wizard: document.getElementById("screen-wizard"),
  diagram: document.getElementById("screen-diagram"),
  euro: document.getElementById("screen-euro"),
  help: document.getElementById("screen-help"),
};

// Верхний прогресс
const topProgressBar = document.getElementById("topProgressBar");
const stepLabel = document.getElementById("stepLabel");

// Пошаговый мастер
const optionCards = document.querySelectorAll(".option-card");
const wizardNextBtn = document.getElementById("wizardNextBtn");
const wizardPrevBtn = document.getElementById("wizardPrevBtn");

// Загрузка файлов
const fileInput = document.getElementById("fileInput");
const uploadList = document.getElementById("uploadList");

// 2D схема
const diagramPalette = document.getElementById("diagramPalette");
const diagramCanvas = document.getElementById("diagramCanvas");
const diagramClearBtn = document.getElementById("diagramClearBtn");
const diagramSaveBtn = document.getElementById("diagramSaveBtn");

// Профиль
const profilePanel = document.getElementById("profilePanel");
const openProfileBtn = document.getElementById("openProfileBtn");
const closeProfileBtn = document.getElementById("closeProfileBtn");
const profileSaveBtn = document.getElementById("profileSaveBtn");
const profileForm = document.getElementById("profileForm");

// Европротокол
const euroForm = document.getElementById("euroForm");
const euroSaveBtn = document.getElementById("euroSaveBtn");

// Мини‑чат
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");

// Переключатель языка
const langSwitch = document.getElementById("langSwitch");
let currentLang = "ru";

// Состояние шагов
let currentStep = 1;
const totalSteps = 4;
let selectedAccidentType = null;

// ----------------------------------------------
// Навигация по основным экранам
// ----------------------------------------------

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const screenName = btn.dataset.screen;

    navButtons.forEach((b) => b.classList.remove("main-nav-btn--active"));
    btn.classList.add("main-nav-btn--active");

    Object.entries(screens).forEach(([name, section]) => {
      section.classList.toggle("screen--active", name === screenName);
    });
  });
});

// ----------------------------------------------
// Прогресс по шагам (вверхняя шкала, кнопки Вперёд/Назад)
// ----------------------------------------------

function updateProgress() {
  const percent = (currentStep / totalSteps) * 100;
  topProgressBar.style.width = percent + "%";
  stepLabel.textContent = `Шаг ${currentStep} из ${totalSteps}`;

  // Кнопка "Назад" неактивна на первом шаге
  wizardPrevBtn.disabled = currentStep === 1;
}
updateProgress();

// Выбор типа происшествия
optionCards.forEach((card) => {
  card.addEventListener("click", () => {
    optionCards.forEach((c) => c.classList.remove("selected"));
    card.classList.add("selected");

    const radio = card.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;

    selectedAccidentType = card.dataset.type;
    wizardNextBtn.disabled = false;
  });
});

// Кнопка "Далее"
wizardNextBtn.addEventListener("click", () => {
  // TODO BACKEND: сохранить шаг и выбранный тип ДТП
  // POST /api/accident/draft  body: { step: currentStep, type: selectedAccidentType }
  console.log("Шаг завершён, тип:", selectedAccidentType);

  if (currentStep < totalSteps) {
    currentStep += 1;
    updateProgress();
  }
});

// Кнопка "Назад"
wizardPrevBtn.addEventListener("click", () => {
  if (currentStep > 1) {
    currentStep -= 1;
    updateProgress();
    // TODO BACKEND: при желании можно подгружать сохранённые данные для шага
  }
});

// ----------------------------------------------
// Загрузка файлов (фото/документы) — заглушка
// ----------------------------------------------

// Отображаем список выбранных файлов
if (fileInput && uploadList) {
  fileInput.addEventListener("change", () => {
    uploadList.innerHTML = "";
    const files = Array.from(fileInput.files || []);
    files.forEach((file) => {
      const li = document.createElement("li");
      li.textContent = `${file.name} (${Math.round(file.size / 1024)} КБ)`;
      uploadList.appendChild(li);
    });

    // TODO BACKEND: отправка файлов на сервер через FormData
    // const formData = new FormData();
    // files.forEach((file) => formData.append('files', file));
    // fetch('/api/accident/files', { method: 'POST', body: formData });
  });
}

// ----------------------------------------------
// 2D схема ДТП
// ----------------------------------------------

function addDiagramItem(type, imageSrc) {
  const placeholder = diagramCanvas.querySelector(".diagram-placeholder");
  if (placeholder) placeholder.remove();

  const item = document.createElement("div");
  item.className = "diagram-item";

  if (type === "impact") {
    item.classList.add("diagram-item--impact");
    item.title = "Место удара";
  } else if (type === "dent") {
    item.classList.add("diagram-item--dent");
    item.title = "Вмятина";
  } else if (type === "car") {
    // Машина с PNG‑моделькой
    item.classList.add("diagram-item--car");
    item.title = "Машина";
    if (imageSrc) {
      item.style.backgroundImage = `url("${imageSrc}")`;
    }
  } else {
    // Прочие объекты текстом
    item.textContent =
      type === "person"
        ? "Человек"
        : type === "scooter"
        ? "Самокат"
        : type === "bike"
        ? "Велосипед"
        : "Объект";
  }

  const rect = diagramCanvas.getBoundingClientRect();
  const x = rect.width / 2 - 20;
  const y = rect.height / 2 - 10;
  item.style.left = x + "px";
  item.style.top = y + "px";

  let isDragging = false;
  let startX, startY;

  item.addEventListener("mousedown", (e) => {
    isDragging = true;
    startX = e.clientX - item.offsetLeft;
    startY = e.clientY - item.offsetTop;
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const newX = e.clientX - startX;
    const newY = e.clientY - startY;
    item.style.left = newX + "px";
    item.style.top = newY + "px";
  });

  document.addEventListener("mouseup", () => {
    isDragging = false;
  });

  diagramCanvas.appendChild(item);
}


diagramPalette.addEventListener("click", (e) => {
  const btn = e.target.closest(".palette-item");
  if (!btn) return;

  const shape = btn.dataset.shape;
  const imageSrc = btn.dataset.image || null; // для машин будет путь к PNG
  addDiagramItem(shape, imageSrc);
});


diagramClearBtn.addEventListener("click", () => {
  diagramCanvas.innerHTML =
    '<span class="diagram-placeholder">Нажмите на элемент слева, чтобы добавить его на схему.</span>';
});

diagramSaveBtn.addEventListener("click", () => {
  const items = diagramCanvas.querySelectorAll(".diagram-item");
  const result = Array.from(items).map((el) => ({
    type: el.classList.contains("diagram-item--impact")
      ? "impact"
      : el.classList.contains("diagram-item--dent")
      ? "dent"
      : el.textContent,
    left: el.style.left,
    top: el.style.top,
  }));

  // TODO BACKEND: отправить JSON схемы на сервер
  // POST /api/accident/diagram  body: { items: result }
  console.log("Схема ДТП:", result);
});

// ----------------------------------------------
// Профиль пользователя
// ----------------------------------------------

openProfileBtn.addEventListener("click", () => {
  profilePanel.classList.add("profile-panel--open");
  profilePanel.setAttribute("aria-hidden", "false");

  // TODO BACKEND: при открытии можно загрузить профиль
  // GET /api/profile
});

if (closeProfileBtn) {
  closeProfileBtn.addEventListener("click", () => {
    profilePanel.classList.remove("profile-panel--open");
    profilePanel.setAttribute("aria-hidden", "true");
  });
}

profileSaveBtn.addEventListener("click", () => {
  const formData = new FormData(profileForm);
  const payload = Object.fromEntries(formData.entries());

  if (payload.password || payload.password_repeat) {
    if (payload.password !== payload.password_repeat) {
      alert("Пароли не совпадают.");
      return;
    }
  }

  // TODO BACKEND: отправить обновлённые данные профиля
  // PUT /api/profile  body: { name, email, phone, password? }
  console.log("Сохранение профиля:", payload);
});

// ----------------------------------------------
// Шаблон европротокола
// ----------------------------------------------

euroSaveBtn.addEventListener("click", () => {
  const formData = new FormData(euroForm);
  const payload = Object.fromEntries(formData.entries());

  // TODO BACKEND: сохранить черновик европротокола
  // POST /api/accident/europrotocol  body: payload
  console.log("Данные европротокола:", payload);
});

// ----------------------------------------------
// Мини‑чат с ассистентом
// ----------------------------------------------

function appendChatMessage(text, type = "user") {
  const div = document.createElement("div");
  div.className = "chat-message";
  if (type === "system") div.classList.add("chat-message--system");
  if (type === "user") div.classList.add("chat-message--user");
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatSendBtn.addEventListener("click", () => {
  const text = chatInput.value.trim();
  if (!text) return;

  appendChatMessage(text, "user");
  chatInput.value = "";

  // TODO BACKEND/ML: запрос к нейросети
  // POST /api/chat  body: { message: text }
  // и вывести ответ ассистента.
  // Здесь просто имитируем ответ.
  setTimeout(() => {
    appendChatMessage(
      "Это пример ответа ассистента. Реальный ответ будет приходить с сервера.",
      "system"
    );
  }, 500);
});

// ----------------------------------------------
// Переключатель языка
// ----------------------------------------------

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

    // TODO BACKEND/I18N: переключение языка приложения
    console.log("Выбран язык:", currentLang);
  });
}

addDiagramItem