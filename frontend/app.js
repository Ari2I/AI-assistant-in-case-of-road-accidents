// ----------------------------------------------
// КОНФИГУРАЦИЯ API
// ----------------------------------------------
// Если используете Live Server (порт 5500) и Django (порт 8000) -> укажите полный URL
// Если Django отдает статику сам (один порт) -> оставьте пустую строку ''
const API_BASE_URL = 'http://127.0.0.1:8000';

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
// История чата для контекста
let chatHistory = [];

// ----------------------------------------------
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ----------------------------------------------

// Получение CSRF токена (требуется для Django POST запросов)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Универсальный запрос к API
async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE_URL}${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP Error: ${response.status}`);
    }
    return await response.json();
}

// ----------------------------------------------
// НАВИГАЦИЯ
// ----------------------------------------------
navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        const screenName = btn.dataset.screen;
        navButtons.forEach((b) => b.classList.remove("main-nav-btn--active"));
        btn.classList.add("main-nav-btn--active");

        Object.entries(screens).forEach(([name, section]) => {
            if(section) section.classList.toggle("screen--active", name === screenName);
        });
    });
});

// ----------------------------------------------
// ПРОГРЕСС ПО ШАГАМ
// ----------------------------------------------
function updateProgress() {
    const percent = (currentStep / totalSteps) * 100;
    if(topProgressBar) topProgressBar.style.width = percent + "%";
    if(stepLabel) stepLabel.textContent = `Шаг ${currentStep} из ${totalSteps}`;
    if(wizardPrevBtn) wizardPrevBtn.disabled = currentStep === 1;
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
        if(wizardNextBtn) wizardNextBtn.disabled = false;
    });
});

// Кнопка "Далее" (СОХРАНЕНИЕ ЧЕРНОВИКА)
if(wizardNextBtn) {
    // Кнопка "Далее" (ЗАМЕНИТЬ ФУНКЦИЮ ВНУТРИ)
    wizardNextBtn.addEventListener("click", async () => {
        try {
            await apiRequest('/api/accident/draft/', 'POST', {
                step: currentStep,
                type: selectedAccidentType
            });
            console.log("Шаг сохранён на сервере");
            if (currentStep < totalSteps) {
                currentStep += 1;
                updateProgress();
            }
        } catch (error) {
            console.error("Ошибка сохранения шага:", error);
            alert("Не удалось сохранить прогресс.");
        }
    });
}

// Кнопка "Назад"
if(wizardPrevBtn) {
    wizardPrevBtn.addEventListener("click", () => {
        if (currentStep > 1) {
            currentStep -= 1;
            updateProgress();
        }
    });
}

// ----------------------------------------------
// ЗАГРУЗКА ФАЙЛОВ
// ----------------------------------------------
if (fileInput && uploadList) {
    fileInput.addEventListener("change", async () => {
        uploadList.innerHTML = "";
        const files = Array.from(fileInput.files || []);

        files.forEach((file) => {
            const li = document.createElement("li");
            li.textContent = `${file.name} (${Math.round(file.size / 1024)} КБ)`;
            uploadList.appendChild(li);
        });

        if (files.length > 0) {
            const formData = new FormData();
            files.forEach((file) => formData.append('files', file));

            try {
                const response = await fetch(`${API_BASE_URL}/api/accident/files/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: formData
                });
                console.log("Файлы загружены:", await response.json());
            } catch (error) {
                console.error("Ошибка загрузки файлов:", error);
            }
        }
    });
}

// ----------------------------------------------
// 2D СХЕМА ДТП
// ----------------------------------------------
function addDiagramItem(type, imageSrc) {
    if(!diagramCanvas) return;
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
        item.classList.add("diagram-item--car");
        item.title = "Машина";
        if (imageSrc) {
            item.style.backgroundImage = `url("${imageSrc}")`;
        }
    } else {
        item.textContent = type === "person" ? "Человек" : type === "scooter" ? "Самокат" : type === "bike" ? "Велосипед" : "Объект";
    }
    const rect = diagramCanvas.getBoundingClientRect();
    const x = rect.width / 2 - 20;
    const y = rect.height / 2 - 10;
    item.style.left = x + "px";
    item.style.top = y + "px";

    // Логика перетаскивания
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
    document.addEventListener("mouseup", () => { isDragging = false; });

    diagramCanvas.appendChild(item);
}

if(diagramPalette) {
    diagramPalette.addEventListener("click", (e) => {
        const btn = e.target.closest(".palette-item");
        if (!btn) return;
        const shape = btn.dataset.shape;
        const imageSrc = btn.dataset.image || null;
        addDiagramItem(shape, imageSrc);
    });
}

if(diagramClearBtn) {
    diagramClearBtn.addEventListener("click", () => {
        if(diagramCanvas) diagramCanvas.innerHTML = 'Нажмите на элемент слева, чтобы добавить его на схему.';
    });
}

if(diagramSaveBtn) {
    diagramSaveBtn.addEventListener("click", async () => {
        if(!diagramCanvas) return;
        const items = diagramCanvas.querySelectorAll(".diagram-item");
        const result = Array.from(items).map((el) => ({
            type: el.classList.contains("diagram-item--impact") ? "impact" : el.classList.contains("diagram-item--dent") ? "dent" : el.textContent,
            left: el.style.left,
            top: el.style.top,
        }));

        // РЕАЛЬНЫЙ ЗАПРОС: Сохранение схемы
        try {
            await apiRequest('/api/accident/diagram/', 'POST', { items: result });
            alert("Схема ДТП сохранена!");
        } catch (error) {
            console.error("Ошибка сохранения схемы:", error);
            alert("Не удалось сохранить схему.");
        }
    });
}

// ----------------------------------------------
// ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
// ----------------------------------------------
if(openProfileBtn) {
    openProfileBtn.addEventListener("click", async () => {
        if(profilePanel) {
            profilePanel.classList.add("profile-panel--open");
            profilePanel.setAttribute("aria-hidden", "false");
        }
        // Загрузка данных профиля
        try {
            const data = await apiRequest('/api/profile/', 'GET');
            if(profileForm) {
                if(data.name) profileForm.querySelector('[name="name"]') && (profileForm.querySelector('[name="name"]').value = data.name);
                if(data.email) profileForm.querySelector('[name="email"]') && (profileForm.querySelector('[name="email"]').value = data.email);
                if(data.phone) profileForm.querySelector('[name="phone"]') && (profileForm.querySelector('[name="phone"]').value = data.phone);
            }
        } catch (error) {
            console.log("Профиль не загружен (возможно, требуется вход)");
        }
    });
}

if(closeProfileBtn) {
    closeProfileBtn.addEventListener("click", () => {
        if(profilePanel) {
            profilePanel.classList.remove("profile-panel--open");
            profilePanel.setAttribute("aria-hidden", "true");
        }
    });
}

if(profileSaveBtn) {
    profileSaveBtn.addEventListener("click", async () => {
        if(!profileForm) return;
        const formData = new FormData(profileForm);
        const payload = Object.fromEntries(formData.entries());

        if (payload.password || payload.password_repeat) {
            if (payload.password !== payload.password_repeat) {
                alert("Пароли не совпадают.");
                return;
            }
        }

        // РЕАЛЬНЫЙ ЗАПРОС: Обновление профиля
        try {
            await apiRequest('/api/profile/', 'PUT', payload);
            alert("Профиль обновлен!");
            if(profilePanel) profilePanel.classList.remove("profile-panel--open");
        } catch (error) {
            console.error("Ошибка обновления профиля:", error);
            alert("Не удалось обновить профиль.");
        }
    });
}

// ----------------------------------------------
// ЕВРОПРОТОКОЛ
// ----------------------------------------------
if(euroSaveBtn) {
    euroSaveBtn.addEventListener("click", async () => {
        if(!euroForm) return;
        const formData = new FormData(euroForm);
        const payload = Object.fromEntries(formData.entries());

        // РЕАЛЬНЫЙ ЗАПРОС: Сохранение европротокола
        try {
            await apiRequest('/api/accident/europrotocol/', 'POST', payload);
            alert("Данные европротокола сохранены!");
        } catch (error) {
            console.error("Ошибка сохранения европротокола:", error);
            alert("Не удалось сохранить данные.");
        }
    });
}

// ----------------------------------------------
// ГЕОЛОКАЦИЯ (ЯНДЕКС)
// ----------------------------------------------
// Добавьте кнопку с id="geoDetectBtn" в HTML формы европротокола
const geoDetectBtn = document.getElementById('geoDetectBtn');
if(geoDetectBtn) {
    geoDetectBtn.addEventListener("click", () => {
        if (!navigator.geolocation) {
            alert('Геолокация не поддерживается вашим браузером');
            return;
        }

        navigator.geolocation.getCurrentPosition(async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const placeInput = document.getElementById('place-input');

            try {
                // РЕАЛЬНЫЙ ЗАПРОС: Геокодирование через Django
                const response = await fetch(`${API_BASE_URL}/api/geocode/yandex/?lat=${lat}&lon=${lon}`);
                if (!response.ok) throw new Error('Ошибка геокодирования');

                const data = await response.json();
                if (placeInput && data.address) {
                    placeInput.value = data.address;
                }
            } catch (error) {
                console.error('Ошибка геолокации:', error);
                alert('Не удалось определить адрес автоматически');
            }
        }, () => {
            alert('Не удалось получить доступ к геолокации');
        });
    });
}

// ----------------------------------------------
// МИНИ-ЧАТ С АССИСТЕНТОМ (ЗАМЕНИТЬ ЭТОТ БЛОК)
// ----------------------------------------------
let chatHistory = []; // Убедитесь, что переменная объявлена

function appendChatMessage(text, type = "user") {
    const div = document.createElement("div");
    div.className = "chat-message";
    if (type === "system") div.classList.add("chat-message--system");
    if (type === "user") div.classList.add("chat-message--user");
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

if(chatSendBtn) {
    chatSendBtn.addEventListener("click", async () => {
        const text = chatInput.value.trim();
        if (!text) return;

        appendChatMessage(text, "user");
        chatInput.value = "";
        chatSendBtn.disabled = true;

        try {
            const data = await apiRequest('/api/chat/', 'POST', {
                message: text,
                history: chatHistory
            });

            appendChatMessage(data.reply, "system");
            chatHistory = data.history || [];
        } catch (error) {
            console.error("Ошибка чата:", error);
            appendChatMessage("Ошибка соединения с сервером.", "system");
        } finally {
            chatSendBtn.disabled = false;
        }
    });
}

// Отправка по Enter
if(chatInput) {
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !chatSendBtn.disabled) {
            chatSendBtn.click();
        }
    });
}

// ----------------------------------------------
// ПЕРЕКЛЮЧАТЕЛЬ ЯЗЫКА
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
        console.log("Выбран язык:", currentLang);
    });
}