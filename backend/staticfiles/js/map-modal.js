class DtpMapModal {
    constructor() {
        this.defaultCenter = [55.751244, 37.618423];
        this.defaultZoom = 12;
        this.map = null;
        this.placemark = null;
        this.selectedCoords = null;
        this.selectedAddress = "";
        this.isReady = false;

        this.modal = document.getElementById("mapModal");
        this.mapContainer = document.getElementById("map");
        this.confirmBtn = document.getElementById("confirmMapSelection");
        this.addressPreview = document.getElementById("mapSelectedAddress");
        this.placeInput = document.getElementById("euroPlace");
        this.openBtn = document.getElementById("detectLocationBtn");

        this.init();
    }

    init() {
        if (!this.modal || !this.mapContainer || !this.openBtn) return;

        this.openBtn.addEventListener("click", () => this.open());

        document.querySelectorAll("[data-close-map-modal]").forEach((button) => {
            button.addEventListener("click", () => this.close());
        });

        if (this.confirmBtn) {
            this.confirmBtn.addEventListener("click", () => this.confirmSelection());
        }

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && this.modal.classList.contains("map-modal--open")) {
                this.close();
            }
        });

        if (typeof ymaps === "undefined") {
            this.setUnavailable();
            return;
        }

        ymaps.ready(() => {
            this.isReady = true;
            this.openBtn.disabled = false;
        });
    }

    setUnavailable() {
        this.isReady = false;
        this.openBtn.disabled = true;
        this.openBtn.textContent = "Карта недоступна";
    }

    open() {
        if (!this.isReady) {
            alert("Карта еще загружается. Попробуйте через несколько секунд.");
            return;
        }

        this.modal.style.display = "block";
        this.modal.classList.add("map-modal--open");
        this.modal.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";

        window.setTimeout(() => this.initMap(), 50);
    }

    close() {
        this.modal.classList.remove("map-modal--open");
        this.modal.setAttribute("aria-hidden", "true");
        this.modal.style.display = "none";
        document.body.style.overflow = "";

        if (this.map) {
            this.map.destroy();
            this.map = null;
        }

        this.placemark = null;
        this.selectedCoords = null;
        this.selectedAddress = "";
        this.updateSelectionState("Нажмите на карту, чтобы выбрать место ДТП.");
    }

    initMap() {
        if (this.map) {
            this.map.destroy();
        }

        this.map = new ymaps.Map(this.mapContainer, {
            center: this.defaultCenter,
            zoom: this.defaultZoom,
            controls: ["zoomControl", "geolocationControl"],
        });

        this.map.events.add("click", (event) => {
            this.selectCoords(event.get("coords"));
        });

        this.updateSelectionState("Нажмите на карту, чтобы выбрать место ДТП.");
        this.tryCenterOnUser();

        window.setTimeout(() => {
            if (this.map) this.map.container.fitToViewport();
        }, 120);
    }

    tryCenterOnUser() {
        if (!navigator.geolocation) return;

        navigator.geolocation.getCurrentPosition(
            (position) => {
                if (!this.map) return;
                const coords = [position.coords.latitude, position.coords.longitude];
                this.map.setCenter(coords, 15);
            },
            () => {},
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 }
        );
    }

    selectCoords(coords) {
        this.selectedCoords = coords;
        this.selectedAddress = "";

        if (this.placemark) {
            this.map.geoObjects.remove(this.placemark);
        }

        this.placemark = new ymaps.Placemark(
            coords,
            { hintContent: "Место ДТП" },
            { preset: "islands#redIcon" }
        );
        this.map.geoObjects.add(this.placemark);

        this.updateSelectionState("Определяем адрес...");

        this.resolveAddress(coords);
    }

    async resolveAddress(coords) {
        const backendAddress = await this.getAddressFromBackend(coords);
        if (backendAddress) {
            this.selectedAddress = backendAddress;
            this.updateSelectionState(this.selectedAddress);
            return;
        }

        const yandexAddress = await this.getAddressFromYandexMaps(coords);
        if (yandexAddress) {
            this.selectedAddress = yandexAddress;
            this.updateSelectionState(this.selectedAddress);
            return;
        }

        this.selectedAddress = "";
        this.updateSelectionState("Не удалось определить адрес. Выберите точку рядом с дорогой или ориентиром.");
    }

    async getAddressFromBackend(coords) {
        try {
            const response = await fetch("/geolocation/api/get_address/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": this.getCsrfToken(),
                },
                body: JSON.stringify({
                    latitude: coords[0],
                    longitude: coords[1],
                }),
            });

            const data = await response.json();
            if (!response.ok) {
                console.warn("Backend geocoder response:", data);
                return "";
            }
            return data.success && data.address ? data.address : "";
        } catch (error) {
            console.error("Backend geocoder error:", error);
            return "";
        }
    }

    async getAddressFromYandexMaps(coords) {
        try {
            const result = await ymaps.geocode(coords, { results: 1 });
            const firstGeoObject = result.geoObjects.get(0);
            return firstGeoObject ? firstGeoObject.getAddressLine() : "";
        } catch (error) {
            console.error("Yandex Maps geocoder error:", error);
            return "";
        }
    }

    getCsrfToken() {
        const tokenInput = document.querySelector("[name=csrfmiddlewaretoken]");
        if (tokenInput) return tokenInput.value;

        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    updateSelectionState(text) {
        if (this.addressPreview) {
            this.addressPreview.textContent = text;
        }
        if (this.confirmBtn) {
            this.confirmBtn.disabled = !this.selectedAddress;
        }
    }

    confirmSelection() {
        if (!this.selectedAddress || !this.placeInput) return;

        this.placeInput.value = this.selectedAddress;
        this.placeInput.dispatchEvent(new Event("input", { bubbles: true }));

        document.dispatchEvent(new CustomEvent("mapLocationSelected", {
            detail: {
                address: this.selectedAddress,
                latitude: this.selectedCoords?.[0],
                longitude: this.selectedCoords?.[1],
            },
        }));

        this.close();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.dtpMap = new DtpMapModal();
});
