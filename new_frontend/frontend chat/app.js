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
const sidebarOverlay = document.getElementById('sidebarOverlay');
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
let chatMessagesHistory = []; // переименовано во избежание конфликта с id="chatHistory"
// let currentChatId = 1;
let isBotResponding = false;
let messageQueue = [];

// ============================================
// УПРАВЛЕНИЕ ИСТОРИЕЙ ЧАТОВ
// ============================================

let currentChatId = Date.now(); // уникальный ID текущего чата
let chats = []; // массив всех чатов

// Загрузка сохранённых чатов из localStorage
function loadChatsFromStorage() {
  const saved = localStorage.getItem('chats');
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      chats = Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.error('Failed to parse chats from storage, resetting', err);
      chats = [];
    }
  }

  // Если нет чатов — создаём дефолтный
  if (!chats || chats.length === 0) {
    currentChatId = Date.now();
    chats = [{
      id: currentChatId,
      title: 'Оформление ДТП',
      date: new Date().toISOString(),
      messages: [],
      euroData: null
    }];
    saveChatsToStorage();
  } else {
    // Устанавливаем текущий чат — первый в списке (самый новый)
    currentChatId = chats[0].id;
  }

  // Загружаем историю текущего чата в рабочую переменную
  const current = chats.find(c => c.id === currentChatId);
  chatMessagesHistory = current && Array.isArray(current.messages) ? [...current.messages] : [];
}

// Сохранение всех чатов в localStorage
function saveChatsToStorage() {
  localStorage.setItem('chats', JSON.stringify(chats));
}

// Сохранение текущего чата
function saveCurrentChat() {
  const chatIndex = chats.findIndex(c => c.id === currentChatId);
  if (chatIndex !== -1) {
    chats[chatIndex].messages = [...chatMessagesHistory];
    chats[chatIndex].euroData = euroData;
    chats[chatIndex].title = generateChatTitle();
    chats[chatIndex].date = new Date().toISOString();
    saveChatsToStorage();
  }
}

// Генерация названия чата по первому сообщению
function generateChatTitle() {
  const firstUserMessage = chatMessagesHistory.find(m => m.type === 'user');
  if (firstUserMessage) {
    const text = firstUserMessage.text.slice(0, 30);
    return text.length < 30 ? text : text + '...';
  }
  return 'Новый чат';
}

// Обновление боковой панели с историей чатов
function renderChatHistory() {
  const historyContainer = document.getElementById('chatHistory');
  if (!historyContainer) return;
  
  historyContainer.innerHTML = '';
  
  chats.slice().reverse().forEach(chat => {
    const historyItem = document.createElement('div');
    historyItem.className = `history-item ${chat.id === currentChatId ? 'history-item--active' : ''}`;
    historyItem.dataset.chatId = chat.id;
    
    const dateStr = formatChatDate(chat.date);
    
    historyItem.innerHTML = `
      <span>💬 ${escapeHtml(chat.title)}</span>
      <span class="history-date">${dateStr}</span>
    `;
    
    historyItem.addEventListener('click', (e) => {
      e.stopPropagation();
      switchToChat(chat.id);
    });
    
    historyContainer.appendChild(historyItem);
  });
}

// Форматирование даты чата
function formatChatDate(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  
  if (date >= today) return t('ui_today');
  if (date >= yesterday) return t('ui_yesterday');
  return date.toLocaleDateString();
}

// Переключение на другой чат
function switchToChat(chatId) {
  // Сохраняем текущий чат перед переключением
  saveCurrentChat();
  
  // Находим нужный чат
  const chat = chats.find(c => c.id === chatId);
  if (!chat) return;
  
  // Переключаем ID
  currentChatId = chat.id;
  
  // Восстанавливаем данные чата
  chatMessagesHistory = [...chat.messages];
  euroData = chat.euroData || {
    date: null,
    place: null,
    carA: null,
    carB: null,
    witnesses: null,
    circumstances: null
  };
  currentStep = null; // сбрасываем активный шаг
  
  // Очищаем контейнер и перерисовываем сообщения
  messagesContainer.innerHTML = '';
  
  if (chat.messages.length === 0) {
    addMessageToUI(t('welcome'), 'assistant', true);
  } else {
    chat.messages.forEach(msg => {
      // Рендерим ранее сохранённые сообщения, но не сохраняем их заново в историю
      addMessageToUI(msg.text, msg.type, false);
    });
  }
  
  // Обновляем активный класс в боковой панели
  renderChatHistory();
  
  showToast(`Загружен чат: ${chat.title}`, 'info');
}

// Создание нового чата
function createNewChat() {
  // Сохраняем текущий чат
  saveCurrentChat();
  
  // Создаём новый чат
  currentChatId = Date.now();
  chatMessagesHistory = [];
  euroData = {
    date: null,
    place: null,
    carA: null,
    carB: null,
    witnesses: null,
    circumstances: null
  };
  currentStep = null;
  
  // Очищаем контейнер и показываем приветствие
  messagesContainer.innerHTML = '';
  // Добавляем новый чат в массив сначала, чтобы при добавлении приветствия
  // saveCurrentChat мог найти чат и сохранить сообщение
  chats.unshift({
    id: currentChatId,
    title: 'Новый чат',
    date: new Date().toISOString(),
    messages: [],
    euroData: null
  });

  // Показываем приветствие и сохраняем его в историю
  addMessageToUI(t('welcome'), 'assistant', true);

  saveChatsToStorage();
  renderChatHistory();

  showToast('Новый чат создан', 'success');
}

// Удаление чата
function deleteChat(chatId) {
  if (chats.length === 1) {
    showToast('Нельзя удалить последний чат', 'warning');
    return;
  }
  
  const chatIndex = chats.findIndex(c => c.id === chatId);
  if (chatIndex === -1) return;
  
  chats.splice(chatIndex, 1);
  
  if (currentChatId === chatId) {
    // Переключаемся на первый доступный чат
    const nextChat = chats[0];
    if (nextChat) {
      switchToChat(nextChat.id);
    } else {
      createNewChat();
    }
  }
  
  saveChatsToStorage();
  renderChatHistory();
  showToast('Чат удалён', 'info');
}

// ==========================
// СХЕМА ДТП (Яндекс.Карты)
// ==========================
const diagramModal = document.getElementById('diagramModal');
const saveDiagramBtn = document.getElementById('saveDiagramBtn');
const clearDiagramBtn = document.getElementById('clearDiagramBtn');
let diagramMap = null;
let diagramMarkers = { carA: null, carB: null };
// Оверлей для рисования и состояние
let diagramOverlay = null;
let isDrawMode = false;
let currentRectId = 0;
let shapes = []; // { id, x, y, w, h, rot, label, geo }

function ensureOverlay() {
  if (diagramOverlay) return diagramOverlay;
  const mapEl = document.getElementById('diagramMap');
  if (!mapEl) return null;
  // Добавляем оверлей прямо в контейнер карты. НЕ перемещаем и не оборачиваем внутренности карты.
  // Убедимся, что контейнер карты позиционирован, чтобы абсолютные дочерние элементы располагались корректно.
  mapEl.style.position = mapEl.style.position || 'relative';
  const overlay = document.createElement('div');
  overlay.className = 'diagram-overlay';
  overlay.style.position = 'absolute';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.right = '0';
  overlay.style.bottom = '0';
  // start hidden so it doesn't cover the map when not in draw mode
  overlay.style.display = 'none';
  mapEl.appendChild(overlay);
  diagramOverlay = overlay;
  return diagramOverlay;
}

function toggleDrawMode(enable) {
  isDrawMode = typeof enable === 'boolean' ? enable : !isDrawMode;
  const overlay = ensureOverlay();
  if (!overlay) return;
  // show/hide overlay so it does not physically cover the map when not drawing
  if (isDrawMode) {
  // Специально не пытаемся делать снимок живой карты (html2canvas)
  // из-за проблем с CORS/tainted-canvas. Вместо этого используем полупрозрачный
  // оверлей — пользователь может ставить и редактировать фигуры, не взаимодействуя
  // с самой картой. При необходимости это можно заменить серверным изображением.
    overlay.style.backgroundImage = '';
    overlay.classList.remove('snapshot');
    overlay.style.display = 'block';
    overlay.classList.add('draw-mode');
  // Мы не вызываем diagramMap.behaviors.disable(), так как в некоторых сборках
  // поведение карты может быть недоступно. Оверлей перехватывает события указателя
  // и предотвращает взаимодействие с картой под ним.

  // При входе в режим рисования превращаем существующие маркеры в перетаскиваемые прямоугольники
    shapes = [];
  // создаём прямоугольники в позициях маркеров на экране
    const overlayRect = overlay.getBoundingClientRect();
    function addRectForPlacemark(placemark, label) {
      if (!placemark) return;
      try {
        const coords = placemark.geometry.getCoordinates();
  // конвертируем lat/lon в глобальные координаты страницы
  const pagePoint = diagramMap.converter.globalToPage(coords);
  // pagePoint — [x, y] относительно страницы; вычисляем относительно оверлея
        const x = pagePoint[0] - overlayRect.left;
        const y = pagePoint[1] - overlayRect.top;
        const el = addRectangleAt(x, y, 120, 60, 0, label);
        const id = parseInt(el.dataset.id);
  // сохраняем заглушку geo — она будет заполнена при сохранении
        const shape = shapes.find(s => s.id === id);
        if (shape) shape.geo = coords;
      } catch (err) {
        console.warn('Не удалось проецировать метку в координаты страницы', err);
      }
    }
    addRectForPlacemark(diagramMarkers.carA, 'Авто A');
    addRectForPlacemark(diagramMarkers.carB, 'Авто B');
  showToast('Режим рисования включён — переместите и вращайте авто-маркеры при необходимости', 'info');

  // разрешаем клик по оверлею для добавления объектов-авто
    overlay.addEventListener('click', onOverlayClickToAddCar);
  } else {
  overlay.classList.remove('draw-mode');
  overlay.style.display = 'none';
  overlay.classList.remove('snapshot');
  overlay.style.backgroundImage = '';
  // удаляем обработчик клика, добавленный в режиме рисования
    overlay.removeEventListener('click', onOverlayClickToAddCar);
    // No need to re-enable behaviors; overlay removal restores interaction.
    showToast('Режим рисования выключён', 'info');
  }
}

function onOverlayClickToAddCar(e) {
  // ignore if click on an existing control/shape
  if (e.target !== e.currentTarget) return;
  const overlay = diagramOverlay;
  if (!overlay) return;
  const rect = overlay.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  // create a car element
  const id = ++currentRectId;
  const car = document.createElement('div');
  car.className = 'diagram-car';
  car.style.left = (x - 22) + 'px';
  car.style.top = (y - 14) + 'px';
  car.dataset.id = id;
  overlay.appendChild(car);
  // make draggable/rotatable (reuse handle by creating a small invisible handle)
  const handle = document.createElement('div');
  handle.style.width = '100%';
  handle.style.height = '100%';
  handle.style.position = 'absolute';
  handle.style.top = '0';
  handle.style.left = '0';
  handle.style.cursor = 'move';
  handle.style.background = 'transparent';
  car.appendChild(handle);
  makeDraggableAndRotatable(car, handle);
  shapes.push({ id, x, y, w: 44, h: 28, rot: 0, label: 'Авто', geo: null });
}

function addRectangleAt(x, y, w = 120, h = 60, rot = 0, label = 'Прямоугольник') {
  const overlay = ensureOverlay();
  if (!overlay) return null;
  const id = ++currentRectId;
  const rect = document.createElement('div');
  rect.className = 'diagram-rect';
  rect.style.left = (x - w / 2) + 'px';
  rect.style.top = (y - h / 2) + 'px';
  rect.style.width = w + 'px';
  rect.style.height = h + 'px';
  rect.style.transform = `rotate(${rot}deg)`;
  rect.dataset.id = id;

  const rotateHandle = document.createElement('div');
  rotateHandle.className = 'rotate-handle';
  rect.appendChild(rotateHandle);

  const lbl = document.createElement('div');
  lbl.className = 'label';
  lbl.textContent = label;
  rect.appendChild(lbl);

  overlay.appendChild(rect);

  // Make draggable
  makeDraggableAndRotatable(rect, rotateHandle);

  shapes.push({ id, x, y, w, h, rot, label, geo: null });
  return rect;
}

function makeDraggableAndRotatable(el, handle) {
  let isDragging = false;
  let isRotating = false;
  let startX = 0, startY = 0;
  let startLeft = 0, startTop = 0;
  let startAngle = 0;

  el.addEventListener('pointerdown', (e) => {
    if (!isDrawMode) return;
    if (e.target === handle) {
      isRotating = true;
      startX = e.clientX;
      startY = e.clientY;
      const transform = getComputedStyle(el).transform;
      // extract rotation
      let angle = 0;
      if (transform && transform !== 'none') {
        const values = transform.split('(')[1].split(')')[0].split(',');
        const a = parseFloat(values[0]);
        const b = parseFloat(values[1]);
        angle = Math.atan2(b, a) * (180 / Math.PI);
      }
      startAngle = angle;
      el.setPointerCapture(e.pointerId);
    } else {
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      startLeft = parseFloat(el.style.left || 0);
      startTop = parseFloat(el.style.top || 0);
      el.setPointerCapture(e.pointerId);
    }
  });

  el.addEventListener('pointermove', (e) => {
    if (!isDrawMode) return;
    if (isDragging) {
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      el.style.left = (startLeft + dx) + 'px';
      el.style.top = (startTop + dy) + 'px';
    }
    if (isRotating) {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const angle = Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI;
      el.style.transform = `rotate(${angle}deg)`;
    }
  });

  el.addEventListener('pointerup', (e) => {
    isDragging = false;
    isRotating = false;
    try { el.releasePointerCapture(e.pointerId); } catch (er) {}
    // update shapes model
    const id = parseInt(el.dataset.id);
    const rect = el.getBoundingClientRect();
    const overlayRect = el.parentElement.getBoundingClientRect();
    const x = rect.left - overlayRect.left + rect.width / 2;
    const y = rect.top - overlayRect.top + rect.height / 2;
    const w = rect.width;
    const h = rect.height;
    const transform = getComputedStyle(el).transform;
    let angle = 0;
    if (transform && transform !== 'none') {
      const values = transform.split('(')[1].split(')')[0].split(',');
      const a = parseFloat(values[0]);
      const b = parseFloat(values[1]);
      angle = Math.atan2(b, a) * (180 / Math.PI);
    }
    const shape = shapes.find(s => s.id === id);
    if (shape) {
      shape.x = x; shape.y = y; shape.w = w; shape.h = h; shape.rot = angle;
    }
  });
}


function initDiagramMap() {
  // Если API не загружен — ничего не делаем (скрипт подключён с defer)
  if (!window.ymaps) return;

  if (diagramMap) return;

  ymaps.ready(() => {
    try {
      diagramMap = new ymaps.Map('diagramMap', {
        center: [55.76, 37.64], // Москва по умолчанию
        zoom: 14,
        controls: ['zoomControl']
      });

      // Добавляем обработчик клика по карте — ставим маркеры по очереди
      diagramMap.events.add('click', function (e) {
        const coords = e.get('coords');
        // Если нет маркера carA — ставим его, иначе ставим carB
        if (!diagramMarkers.carA) {
          const placemark = new ymaps.Placemark(coords, { hintContent: 'Автомобиль A' }, { preset: 'islands#redVehicleIcon' });
          diagramMap.geoObjects.add(placemark);
          diagramMarkers.carA = placemark;
        } else if (!diagramMarkers.carB) {
          const placemark = new ymaps.Placemark(coords, { hintContent: 'Автомобиль B' }, { preset: 'islands#blueVehicleIcon' });
          diagramMap.geoObjects.add(placemark);
          diagramMarkers.carB = placemark;
        } else {
          // Если оба маркера выставлены — заменяем ближайший
          const distA = ymaps.coordSystem.geo.getDistance(diagramMarkers.carA.geometry.getCoordinates(), coords);
          const distB = ymaps.coordSystem.geo.getDistance(diagramMarkers.carB.geometry.getCoordinates(), coords);
          const replaceKey = distA < distB ? 'carA' : 'carB';
          const newPlacemark = new ymaps.Placemark(coords, { hintContent: replaceKey === 'carA' ? 'Автомобиль A' : 'Автомобиль B' }, { preset: replaceKey === 'carA' ? 'islands#redVehicleIcon' : 'islands#blueVehicleIcon' });
          diagramMap.geoObjects.remove(diagramMarkers[replaceKey]);
          diagramMap.geoObjects.add(newPlacemark);
          diagramMarkers[replaceKey] = newPlacemark;
        }
      });
      // Ensure converter exists (some ymaps builds expose converter on Map)
      if (!diagramMap.converter && ymaps.layout) {
        // nothing to do, converter should exist after render
      }
    } catch (err) {
      console.error('Diagram map init error', err);
    }
  });
}

function openDiagramModal() {
  if (diagramModal) diagramModal.classList.add('modal--visible');
  // Инициализация карты (попробуем через несколько сотен мс если API ещё не готов)
  setTimeout(() => {
    initDiagramMap();
    // ensure overlay exists for drawing
    ensureOverlay();
    // If euroData already has diagram coords (from previous save), restore markers
    try {
      if (euroData && euroData.diagram) {
        const d = euroData.diagram;
        if (d.carA && d.carA.length === 2) {
          if (!diagramMarkers.carA) {
            const placemark = new ymaps.Placemark(d.carA, { hintContent: 'Автомобиль A' }, { preset: 'islands#redVehicleIcon' });
            diagramMap.geoObjects.add(placemark);
            diagramMarkers.carA = placemark;
          } else {
            diagramMarkers.carA.geometry.setCoordinates(d.carA);
          }
        }
        if (d.carB && d.carB.length === 2) {
          if (!diagramMarkers.carB) {
            const placemark = new ymaps.Placemark(d.carB, { hintContent: 'Автомобиль B' }, { preset: 'islands#blueVehicleIcon' });
            diagramMap.geoObjects.add(placemark);
            diagramMarkers.carB = placemark;
          } else {
            diagramMarkers.carB.geometry.setCoordinates(d.carB);
          }
        }
      }
    } catch (err) {
      // ignore restore errors
    }
  }, 200);
}

function clearDiagram() {
  // clear map and overlay shapes
  if (!diagramMap) {
    diagramMarkers = { carA: null, carB: null };
    const mapEl = document.getElementById('diagramMap');
    if (mapEl) mapEl.innerHTML = '';
  } else {
    diagramMap.geoObjects.removeAll();
    diagramMarkers = { carA: null, carB: null };
  }
  // remove overlay rectangles
  if (diagramOverlay) {
    diagramOverlay.innerHTML = '';
    shapes = [];
    currentRectId = 0;
  }
}

function saveDiagram() {
  // Сохраняем координаты в euroData и в историю чата как заметку
  const carAPos = diagramMarkers.carA ? diagramMarkers.carA.geometry.getCoordinates() : null;
  const carBPos = diagramMarkers.carB ? diagramMarkers.carB.geometry.getCoordinates() : null;

  // Convert shapes' pixel centers to geo coordinates (lat, lon)
  const overlay = ensureOverlay();
  const overlayRect = overlay ? overlay.getBoundingClientRect() : null;
  const convertedShapes = shapes.map(s => {
    // try rectangle element first, then car element
    let el = document.querySelector(`.diagram-rect[data-id="${s.id}"]`);
    let isCar = false;
    if (!el) {
      el = document.querySelector(`.diagram-car[data-id="${s.id}"]`);
      if (el) isCar = true;
    }
    if (!el || !diagramMap || !overlayRect) return Object.assign({}, s);
    const rect = el.getBoundingClientRect();
    const centerX = rect.left - overlayRect.left + rect.width / 2;
    const centerY = rect.top - overlayRect.top + rect.height / 2;
    // page coords expected by converter: [x, y]
    try {
      const pageX = overlayRect.left + centerX;
      const pageY = overlayRect.top + centerY;
      const geo = diagramMap.converter.pageToGlobal([pageX, pageY]);
      // for cars, save type
      const base = Object.assign({}, s, { geo });
      if (isCar) base.type = 'car';
      return base;
    } catch (err) {
      console.warn('Failed to convert page to geo', err);
      return Object.assign({}, s);
    }
  });

  euroData.diagram = {
    carA: carAPos,
    carB: carBPos,
    shapes: convertedShapes,
    timestamp: new Date().toISOString()
  };

  // Добавляем сообщение в чат с кратким описанием и ссылкой на координаты
  const summary = `Схема ДТП сохранена. A: ${carAPos ? carAPos.map(c => c.toFixed(5)).join(',') : 'не указано'}; B: ${carBPos ? carBPos.map(c => c.toFixed(5)).join(',') : 'не указано'}`;
  addMessageToUI(summary, 'assistant', true);
  showToast('Схема сохранена', 'success');
  closeAllModals();
}


// Добавляем кнопку удаления чата (опционально, при наведении на элемент истории)
function addDeleteButtonToHistory() {
  // Можно добавить долгое нажатие или иконку корзины
  // Для простоты: двойной клик по элементу истории удаляет чат
  const historyItems = document.querySelectorAll('.history-item');
  historyItems.forEach(item => {
    item.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      const chatId = parseInt(item.dataset.chatId);
      if (confirm('Удалить этот чат?')) {
        deleteChat(chatId);
      }
    });
  });
}

// ============================================
// БЕЗОПАСНОСТЬ: экранирование HTML
// ============================================
function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatMarkdown(text) {
  // Сначала экранируем HTML
  let safeText = escapeHtml(text);
  // Затем применяем безопасное форматирование
  safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  safeText = safeText.replace(/`(.*?)`/g, '<code>$1</code>');
  safeText = safeText.replace(/\n/g, '<br>');
  return safeText;
}

// ============================================
// TOAST-УВЕДОМЛЕНИЯ (вместо alert)
// ============================================
function showToast(message, type = 'info') {
  const existingToast = document.querySelector('.toast');
  if (existingToast) existingToast.remove();
  
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('toast--show');
  }, 10);
  
  setTimeout(() => {
    toast.classList.remove('toast--show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ============================================
// ПЕРЕВОДЫ (полные)
// ============================================
const translations = {
  ru: {
    // UI элементы
    ui_title: "ДТП Ассистент",
    ui_subtitle: "AI помощник",
    ui_profile: "Профиль",
    ui_new_chat: "Новый чат",
    ui_today: "Сегодня",
    ui_yesterday: "Вчера",
    ui_online: "онлайн",
    ui_placeholder: "Напишите сообщение...",
    ui_hint: "AI может ошибаться. Для точной информации обращайтесь в страховую.",
    
    // Быстрые действия
    quick_euro: "📋 Оформить европротокол",
    quick_photo: "📸 Как правильно сфотографировать?",
    quick_payout: "💰 Рассчитать выплату",
    quick_deadline: "⏰ Сроки подачи документов",
    quick_call: "🚨 Вызвать экстренные службы",
    
    // Сообщения чата
    welcome: "Здравствуйте! Я ваш AI помощник по оформлению ДТП. 🚗\n\nЯ помогу вам:\n✅ Оформить европротокол по шагам\n✅ Сделать правильную фотофиксацию\n✅ Заполнить все необходимые документы\n✅ Рассчитать примерную выплату по ОСАГО\n\n👉 Выберите действие ниже или просто напишите свой вопрос",
    euro_start: "Отлично! Давайте оформим европротокол. Я буду задавать вам вопросы, а вы отвечайте. Начнём?",
    euro_question_1: "📅 **Шаг 1 из 6:** Укажите дату и время ДТП (например: 10.04.2026 15:30)",
    euro_question_2: "📍 **Шаг 2 из 6:** Где произошло ДТП? (город, улица, ориентиры)",
    euro_question_3: "🚗 **Шаг 3 из 6:** Данные вашего автомобиля (автомобиль А). Укажите: госномер и ФИО владельца через запятую",
    euro_question_4: "🚙 **Шаг 4 из 6:** Данные второго автомобиля (автомобиль Б). Укажите: госномер и ФИО владельца через запятую",
    euro_question_5: "👥 **Шаг 5 из 6:** Есть ли свидетели? Если да, укажите ФИО и контакты (если нет, напишите 'нет')",
    euro_question_6: "📝 **Шаг 6 из 6:** Кратко опишите обстоятельства ДТП (кто двигался, кто нарушил, и т.д.)",
    euro_success: "✅ **Отлично! Данные европротокола сохранены!**\n\n📅 Дата: {date}\n📍 Место: {place}\n🚗 Авто А: {carA}\n🚙 Авто Б: {carB}\n👥 Свидетели: {witnesses}\n📝 Обстоятельства: {circumstances}\n\n**Что делать дальше:**\n1. 📸 Сделайте фото места ДТП и повреждений\n2. 📄 Заполните бумажный бланк европротокола\n3. 📷 Сфотографируйте заполненный бланк\n4. 🏦 Отправьте всё в страховую в течение 5 дней\n\nХотите, я рассчитаю примерную выплату? Или помогу с фотофиксацией?",
    photo_guide: "📸 **Как правильно сфотографировать место ДТП:**\n\n1️⃣ **Общий план** — место ДТП с высоты, видны оба авто и дорога\n2️⃣ **Расположение** — авто относительно разметки, знаков, светофоров\n3️⃣ **Повреждения** — крупным планом, со всех ракурсов\n4️⃣ **Госномера** — обоих автомобилей\n5️⃣ **Документы** — заполненный европротокол\n\n👉 Нажмите на скрепку 📎 внизу, чтобы загрузить фото, или сделайте фото прямо сейчас.",
    payout_calc: "💰 **Расчёт примерной выплаты по ОСАГО**\n\nМаксимальная сумма по европротоколу: **100 000 ₽**\n(до 400 000 ₽ в Москве, СПб и областях)\n\n**Факторы, влияющие на выплату:**\n• Износ деталей — до 50%\n• Стоимость работ по среднерыночным ценам\n• Наличие фотофиксации\n\n📌 Для точного расчёта отправьте фото повреждений в чат — я помогу оценить.\n\nХотите узнать, как увеличить сумму выплаты?",
    deadlines: "⏰ **Сроки подачи документов в страховую**\n\n⚠️ **Важно!** Документы нужно подать в течение **5 рабочих дней** после ДТП.\n\n**Что нужно подать:**\n1. Заявление о страховом случае\n2. Заполненный европротокол\n3. Фото/видео материалы\n4. Паспорт и права\n5. Реквизиты для перевода\n\nОпоздание может стать причиной отказа в выплате!",
    emergency: "🚨 **Вызов экстренных служб**\n\nНажмите на кнопку вызова ниже, чтобы позвонить:\n\n• **112** — единый номер экстренных служб\n• **102** — полиция\n• **103** — скорая помощь\n\n⚠️ Звоните только в случае реальной необходимости!",
    photo_received: "📸 Спасибо за фото! Я сохранил {count} снимков. Они помогут при оформлении страхового случая.\n\nХотите добавить ещё фото или продолжить оформление?",
    unknown: "Я не совсем понял. Выберите действие из предложенных ниже или напишите 'помощь' для списка команд.\n\nДоступные команды:\n• европротокол / euro — начать оформление\n• фото / photo — инструкция по фотофиксации\n• выплата / payout — рассчитать выплату\n• сроки / deadline — сроки подачи\n• помощь / help — показать это сообщение",
    profile_saved: "👤 Профиль сохранён! Теперь я могу использовать ваши данные при оформлении.",
    chat_copied: "📋 История чата скопирована в буфер обмена",
    copy_failed: "❌ Не удалось скопировать историю чата",
    no_photos: "📸 Пожалуйста, выберите фото для загрузки",
    clear_chat: "Чат очищен. Начнём заново? Задайте вопрос или выберите действие."
  },
  en: {
    ui_title: "Accident Assistant",
    ui_subtitle: "AI Assistant",
    ui_profile: "Profile",
    ui_new_chat: "New Chat",
    ui_today: "Today",
    ui_yesterday: "Yesterday",
    ui_online: "online",
    ui_placeholder: "Type a message...",
    ui_hint: "AI may make mistakes. For accurate information, contact your insurance company.",
    
    quick_euro: "📋 Complete Europrotocol",
    quick_photo: "📸 How to take proper photos?",
    quick_payout: "💰 Calculate payout",
    quick_deadline: "⏰ Submission deadlines",
    quick_call: "🚨 Call emergency services",
    
    welcome: "Hello! I'm your AI assistant for accident reporting. 🚗\n\nI can help you:\n✅ Complete Europrotocol step by step\n✅ Take proper photos of the scene\n✅ Fill out all necessary documents\n✅ Calculate approximate insurance payout\n\n👉 Choose an action below or just type your question",
    euro_start: "Great! Let's complete the Europrotocol. I'll ask you questions, just answer them. Shall we start?",
    euro_question_1: "📅 **Step 1 of 6:** Enter the date and time of the accident (e.g., 04/10/2026 15:30)",
    euro_question_2: "📍 **Step 2 of 6:** Where did the accident happen? (city, street, landmarks)",
    euro_question_3: "🚗 **Step 3 of 6:** Your vehicle details (Vehicle A): license plate and owner's full name",
    euro_question_4: "🚙 **Step 4 of 6:** Other vehicle details (Vehicle B): license plate and owner's full name",
    euro_question_5: "👥 **Step 5 of 6:** Are there witnesses? If yes, provide names and contacts (if no, write 'none')",
    euro_question_6: "📝 **Step 6 of 6:** Briefly describe the circumstances of the accident",
    euro_success: "✅ **Great! Europrotocol data saved!**\n\n📅 Date: {date}\n📍 Place: {place}\n🚗 Vehicle A: {carA}\n🚙 Vehicle B: {carB}\n👥 Witnesses: {witnesses}\n📝 Circumstances: {circumstances}\n\n**Next steps:**\n1. 📸 Take photos of the scene and damages\n2. 📄 Fill out the paper Europrotocol form\n3. 📷 Take photos of the completed form\n4. 🏦 Submit everything to insurance within 5 days\n\nWould you like me to calculate an approximate payout? Or help with photos?",
    photo_guide: "📸 **How to properly photograph the accident scene:**\n\n1️⃣ **Overall view** — shows both cars and the road\n2️⃣ **Position** — cars relative to markings, signs, traffic lights\n3️⃣ **Damages** — close-ups from all angles\n4️⃣ **License plates** — of both vehicles\n5️⃣ **Documents** — completed Europrotocol form\n\n👉 Click the paperclip 📎 below to upload photos, or take a photo right now.",
    payout_calc: "💰 **Approximate insurance payout calculation**\n\nMaximum amount under Europrotocol: **$1,200 USD**\n\n**Factors affecting payout:**\n• Parts depreciation — up to 50%\n• Labor costs at market rates\n• Quality of photo documentation\n\n📌 For accurate calculation, send photos of damages to chat — I'll help assess.\n\nWant to know how to increase your payout?",
    deadlines: "⏰ **Deadlines for submitting documents to insurance**\n\n⚠️ **Important!** Documents must be submitted within **5 business days** after the accident.\n\n**What to submit:**\n1. Insurance claim application\n2. Completed Europrotocol\n3. Photo/video materials\n4. Passport and driver's license\n5. Bank details for transfer\n\nMissing the deadline may result in refusal of payment!",
    emergency: "🚨 **Emergency services call**\n\nClick the call button below to dial:\n\n• **112** — unified emergency number\n• **102** — police\n• **103** — ambulance\n\n⚠️ Only call if truly necessary!",
    photo_received: "📸 Thank you for the photos! I saved {count} images. They will help with your insurance claim.\n\nWould you like to add more photos or continue with the process?",
    unknown: "I didn't quite understand. Choose an action from the options below or type 'help' for available commands.\n\nAvailable commands:\n• europrotocol / euro — start Europrotocol\n• photo — photo instructions\n• payout — calculate payout\n• deadline — submission deadlines\n• help — show this message",
    profile_saved: "👤 Profile saved! I can now use your data during the process.",
    chat_copied: "📋 Chat history copied to clipboard",
    copy_failed: "❌ Failed to copy chat history",
    no_photos: "📸 Please select photos to upload",
    clear_chat: "Chat cleared. Shall we start over? Ask a question or choose an action."
  }
};

function t(key, replacements = {}) {
  let text = translations[currentLang][key] || translations.ru[key] || key;
  for (const [k, v] of Object.entries(replacements)) {
    text = text.replace(`{${k}}`, v);
  }
  return text;
}

// ============================================
// ОБНОВЛЕНИЕ UI ПРИ СМЕНЕ ЯЗЫКА
// ============================================
function updateUILanguage() {
  // Обновляем HTML lang
  document.documentElement.lang = currentLang;
  
  // Заголовок страницы
  document.title = t('ui_title');
  
  // Логотип
  const logoTitle = document.querySelector('.logo-title');
  const logoSub = document.querySelector('.logo-sub');
  if (logoTitle) logoTitle.textContent = t('ui_title');
  if (logoSub) logoSub.textContent = t('ui_subtitle');
  
  // Кнопки
  const newChatBtnText = document.querySelector('.new-chat-btn span');
  if (newChatBtnText) newChatBtnText.textContent = t('ui_new_chat');
  
  const profileBtnText = document.querySelector('.profile-btn span');
  if (profileBtnText) profileBtnText.textContent = t('ui_profile');
  
  // Статус ассистента
  const assistantStatus = document.querySelector('.assistant-details p');
  if (assistantStatus) assistantStatus.textContent = t('ui_online');
  
  // Плейсхолдер ввода
  if (messageInput) messageInput.placeholder = t('ui_placeholder');
  
  // Подсказка внизу
  const inputHint = document.querySelector('.input-hint');
  if (inputHint) inputHint.textContent = t('ui_hint');
  
  // Быстрые действия
  const quickChips = document.querySelectorAll('.quick-action-chip');
  const quickActionsMap = {
    euro: t('quick_euro'),
    photo: t('quick_photo'),
    payout: t('quick_payout'),
    deadline: t('quick_deadline'),
    call: t('quick_call')
  };
  quickChips.forEach(chip => {
    const action = chip.dataset.action;
    if (quickActionsMap[action]) {
      chip.innerHTML = quickActionsMap[action];
    }
  });
  
  // История чатов (даты)
  document.querySelectorAll('.history-date').forEach((el, idx) => {
    el.textContent = idx === 0 ? t('ui_today') : t('ui_yesterday');
  });
}

// ============================================
// ОЧЕРЕДЬ СООБЩЕНИЙ (фикс race condition)
// ============================================
async function processQueue() {
  if (isBotResponding || messageQueue.length === 0) return;
  isBotResponding = true;
  
  // Блокируем ввод
  if (sendBtn) sendBtn.disabled = true;
  if (messageInput) messageInput.disabled = true;
  
  const { text, isUser } = messageQueue.shift();

if (isUser) {
  addMessageToUI(text, 'user');
  // Не показываем typing и не дублируем сообщение как ответ бота
  isBotResponding = false;
  processQueue();
  return;
}

// Только для ответов бота показываем печать
await showTyping(1000);
addMessageToUI(text, 'assistant');
  
  // Разблокируем
  if (sendBtn) sendBtn.disabled = false;
  if (messageInput) messageInput.disabled = false;
  if (messageInput) messageInput.focus();
  
  isBotResponding = false;
  processQueue();
}

function queueAssistantResponse(text) {
  messageQueue.push({ text, isUser: false });
  processQueue();
}

function addMessageToUI(text, type = 'assistant', saveToHistory = true) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message--${type}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = type === 'assistant' ? '🤖' : '👤';

  const content = document.createElement('div');
  content.className = 'message-content';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  bubble.innerHTML = formatMarkdown(text);
  content.appendChild(bubble);
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(content);

  if (messagesContainer) messagesContainer.appendChild(messageDiv);
  scrollToBottom();

  // Сохраняем в историю чата (если нужно)
  if (saveToHistory) {
    chatMessagesHistory.push({
      type,
      text,
      timestamp: new Date().toISOString()
    });
    // Автосохранение при добавлении сообщения
    setTimeout(() => saveCurrentChat(), 100);
  }
}

async function showTyping(duration = 1500) {
  typingIndicator.style.display = 'block';
  scrollToBottom();
  await new Promise(resolve => setTimeout(resolve, duration));
  typingIndicator.style.display = 'none';
}

function scrollToBottom() {
  const chatArea = document.getElementById('chatMessagesArea');
  if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
}

// ============================================
// ОБРАБОТКА СООБЩЕНИЙ
// ============================================
function processUserMessage(message) {
  const lowerMsg = message.toLowerCase().trim();
  
  if (currentStep) {
    processEuroStep(message);
    return;
  }
  
  if (lowerMsg === 'помощь' || lowerMsg === 'help') {
    queueAssistantResponse(t('unknown'));
    return;
  }
  
  if (lowerMsg.includes('европротокол') || lowerMsg.includes('euro') || lowerMsg === 'начать' || lowerMsg === 'start') {
    startEuroprotocol();
    return;
  }
  
  if (lowerMsg.includes('фото') || lowerMsg.includes('photo')) {
    queueAssistantResponse(t('photo_guide'));
    setTimeout(() => openModal(photoModal), 1000);
    return;
  }
  
  if (lowerMsg.includes('выплат') || lowerMsg.includes('payout') || lowerMsg.includes('расчёт')) {
    queueAssistantResponse(t('payout_calc'));
    return;
  }
  
  if (lowerMsg.includes('срок') || lowerMsg.includes('deadline') || lowerMsg.includes('подач')) {
    queueAssistantResponse(t('deadlines'));
    return;
  }
  
  if (lowerMsg.includes('вызов') || lowerMsg.includes('call') || lowerMsg.includes('112')) {
    queueAssistantResponse(t('emergency'));
    setTimeout(() => openModal(callModal), 500);
    return;
  }
  
  queueAssistantResponse(t('unknown'));
}

async function startEuroprotocol() {
  currentStep = 1;
  euroData = {
    date: null,
    place: null,
    carA: null,
    carB: null,
    witnesses: null,
    circumstances: null
  };
  queueAssistantResponse(t('euro_start'));
  queueAssistantResponse(t('euro_question_1')); // без setTimeout
}

function processEuroStep(message) {
  switch (currentStep) {
    case 1:
      euroData.date = message;
      currentStep = 2;
      queueAssistantResponse(t('euro_question_2'));
      break;
    case 2:
      euroData.place = message;
      currentStep = 3;
      queueAssistantResponse(t('euro_question_3'));
      break;
    case 3:
      euroData.carA = message;
      currentStep = 4;
      queueAssistantResponse(t('euro_question_4'));
      break;
    case 4:
      euroData.carB = message;
      currentStep = 5;
      queueAssistantResponse(t('euro_question_5'));
      break;
    case 5:
      euroData.witnesses = message;
      currentStep = 6;
      queueAssistantResponse(t('euro_question_6'));
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
      queueAssistantResponse(successMsg);
      
      const reports = JSON.parse(localStorage.getItem('euroReports') || '[]');
      reports.push({ ...euroData, timestamp: new Date().toISOString() });
      localStorage.setItem('euroReports', JSON.stringify(reports));
      break;
  }
}

// ============================================
// ОТПРАВКА СООБЩЕНИЯ
// ============================================
function sendMessage() {
  if (isBotResponding) {
    showToast('Подождите, бот отвечает...', 'warning');
    return;
  }
  
  const message = messageInput.value.trim();
  if (!message) return;
  
  messageQueue.push({ text: message, isUser: true });
  messageInput.value = '';
  autoResizeTextarea();
  
  processUserMessage(message);
  
  // Автосохранение после отправки сообщения
  setTimeout(() => saveCurrentChat(), 100);
}

// ============================================
// AUTO-RESIZE ДЛЯ TEXTAREA
// ============================================
function autoResizeTextarea() {
  if (messageInput) {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
  }
}

// ============================================
// НОВЫЙ ЧАТ
// ============================================
// Обработчик для кнопки "Новый чат"
if (newChatBtn) {
  newChatBtn.addEventListener('click', () => {
    createNewChat();
  });
}

// Удаляем старую функцию resetChat, используем createNewChat

// ============================================
// МОДАЛЬНЫЕ ОКНА
// ============================================
function openModal(modal) {
  if (modal) modal.classList.add('modal--visible');
}

function closeAllModals() {
  document.querySelectorAll('.modal').forEach(modal => {
    modal.classList.remove('modal--visible');
  });
}

function handlePhotoFiles(files) {
  pendingPhotos = [];
  if (photoPreviewList) photoPreviewList.innerHTML = '';
  
  Array.from(files).forEach(file => {
    if (file.type.startsWith('image/')) {
      pendingPhotos.push(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = document.createElement('img');
        img.src = e.target.result;
        img.className = 'photo-preview';
        if (photoPreviewList) photoPreviewList.appendChild(img);
      };
      reader.readAsDataURL(file);
    }
  });
}

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
  closeAllModals();
  queueAssistantResponse(t('profile_saved'));
}

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ
// ============================================

// Отправка сообщения
if (sendBtn) sendBtn.addEventListener('click', sendMessage);
if (messageInput) {
  messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  messageInput.addEventListener('input', autoResizeTextarea);
}

// Быстрые действия
quickActionChips.forEach(chip => {
  chip.addEventListener('click', () => {
    const action = chip.dataset.action;
    switch (action) {
      case 'diagram':
        queueAssistantResponse(t('photo_guide'));
        setTimeout(() => openDiagramModal(), 500);
        break;
      case 'euro':
        startEuroprotocol();
        break;
      case 'photo':
        queueAssistantResponse(t('photo_guide'));
        setTimeout(() => openModal(photoModal), 1000);
        break;
      case 'payout':
        queueAssistantResponse(t('payout_calc'));
        break;
      case 'deadline':
        queueAssistantResponse(t('deadlines'));
        break;
      case 'call':
        queueAssistantResponse(t('emergency'));
        setTimeout(() => openModal(callModal), 500);
        break;
    }
  });
});

// Прикрепление файлов
if (attachBtn) {
  attachBtn.addEventListener('click', () => openModal(photoModal));
}

if (modalFileInput) {
  modalFileInput.addEventListener('change', (e) => handlePhotoFiles(e.target.files));
}

if (modalCameraInput) {
  modalCameraInput.addEventListener('change', (e) => handlePhotoFiles(e.target.files));
}

if (photoSubmitBtn) {
  photoSubmitBtn.addEventListener('click', async () => {
    if (pendingPhotos.length > 0) {
      closeAllModals();
      queueAssistantResponse(t('photo_received', { count: pendingPhotos.length }));
      pendingPhotos = [];
    } else {
      showToast(t('no_photos'), 'warning');
    }
  });
}

// Мобильное меню с оверлеем
if (mobileMenuBtn) {
  mobileMenuBtn.addEventListener('click', () => {
    sidebar.classList.add('sidebar--open');
    if (sidebarOverlay) sidebarOverlay.classList.add('sidebar-overlay--visible');
  });
}

function closeSidebar() {
  sidebar.classList.remove('sidebar--open');
  if (sidebarOverlay) sidebarOverlay.classList.remove('sidebar-overlay--visible');
}

if (sidebarOverlay) {
  sidebarOverlay.addEventListener('click', closeSidebar);
}

// Новый чат
// Нажатие на кнопку "Новый чат" уже навешено выше (createNewChat). Убираем старые/неопределённые вызовы.

// Профиль
if (openProfileBtn) {
  openProfileBtn.addEventListener('click', () => {
    loadProfile();
    openModal(profileModal);
  });
}

if (profileSaveBtn) profileSaveBtn.addEventListener('click', saveProfile);

// Поделиться чатом
if (shareChatBtn) {
  shareChatBtn.addEventListener('click', async () => {
    const chatText = chatMessagesHistory.map(m => `${m.type === 'user' ? '👤' : '🤖'}: ${m.text}`).join('\n\n');
    try {
      await navigator.clipboard.writeText(chatText);
      showToast(t('chat_copied'), 'success');
    } catch (err) {
      showToast(t('copy_failed'), 'error');
    }
  });
}

// Экстренные вызовы
function setupEmergencyCalls() {
  const emergencyCards = document.querySelectorAll('.emergency-card');
  emergencyCards.forEach(card => {
    card.setAttribute('role', 'button');
    card.setAttribute('tabindex', '0');
    card.addEventListener('click', () => {
      const number = card.dataset.number;
      if (number) window.location.href = `tel:${number}`;
    });
    card.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const number = card.dataset.number;
        if (number) window.location.href = `tel:${number}`;
      }
    });
  });
}

// Закрытие модалок
modalCloses.forEach(btn => {
  btn.addEventListener('click', closeAllModals);
});

// Слушатели для схемы ДТП
if (saveDiagramBtn) saveDiagramBtn.addEventListener('click', saveDiagram);
if (clearDiagramBtn) clearDiagramBtn.addEventListener('click', () => {
  clearDiagram();
  showToast('Схема очищена', 'info');
});

// Draw mode control (toggle only)
const toggleDrawBtn = document.getElementById('toggleDrawBtn');

if (toggleDrawBtn) toggleDrawBtn.addEventListener('click', () => toggleDrawMode());

document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeAllModals();
  });
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeAllModals();
    closeSidebar();
  }
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
    
    updateUILanguage();
    showToast(`Language switched to ${currentLang === 'ru' ? 'Russian' : 'English'}`, 'info');
  });
}

// Инициализация: сначала загружаем историю чатов и переключаемся на текущий
loadChatsFromStorage();
renderChatHistory();
if (chats && chats.length > 0) {
  switchToChat(currentChatId);
} else {
  createNewChat();
}

// Далее настраиваем UI и вспомогательные обработчики
setupEmergencyCalls();
updateUILanguage();

// Сохранение черновика
window.addEventListener('beforeunload', () => {
  if (euroData.date || euroData.place) {
    localStorage.setItem('draftEuroData', JSON.stringify(euroData));
  }
});

console.log('✅ Чат ассистент готов к работе!');

// Добавляем обработчики для удаления (после рендера)
setTimeout(addDeleteButtonToHistory, 100);