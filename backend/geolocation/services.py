from typing import Optional, Dict

import requests
from django.conf import settings


class YandexGeocoderService:
    """Reverse geocoding service for accident location selection."""

    YANDEX_URL = "https://geocode-maps.yandex.ru/1.x/"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

    @property
    def api_key(self):
        key = settings.YANDEX_GEOCODER_API_KEY
        if not key:
            raise ValueError("YANDEX_GEOCODER_API_KEY is not configured")
        return key

    def get_address_by_coords(self, latitude: float, longitude: float) -> Optional[str]:
        address = self._get_yandex_address_by_coords(latitude, longitude)
        if address:
            return address

        return self._get_osm_address_by_coords(latitude, longitude)

    def get_coords_by_address(self, address: str) -> Optional[Dict[str, float]]:
        try:
            response = requests.get(
                self.YANDEX_URL,
                params={
                    "apikey": self.api_key,
                    "geocode": address,
                    "format": "json",
                    "lang": "ru_RU",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            geo_objects = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
            if not geo_objects:
                return None

            geo_object = geo_objects[0].get("GeoObject", {})
            pos = geo_object.get("Point", {}).get("pos", "")
            if not pos:
                return None

            lng, lat = pos.split()
            return {"lat": float(lat), "lng": float(lng)}

        except requests.RequestException as exc:
            self._log_request_error("Yandex forward geocoder", exc)
            return None

    def _get_yandex_address_by_coords(self, latitude: float, longitude: float) -> Optional[str]:
        try:
            response = requests.get(
                self.YANDEX_URL,
                params={
                    "apikey": self.api_key,
                    "geocode": f"{longitude},{latitude}",
                    "format": "json",
                    "lang": "ru_RU",
                    "results": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            geo_objects = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
            if not geo_objects:
                return None

            geo_object = geo_objects[0].get("GeoObject", {})
            geocoder_meta = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
            address = self._format_yandex_address(geocoder_meta)
            return address or None

        except requests.RequestException as exc:
            self._log_request_error("Yandex reverse geocoder", exc)
            return None

    def _get_osm_address_by_coords(self, latitude: float, longitude: float) -> Optional[str]:
        try:
            response = requests.get(
                self.NOMINATIM_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "jsonv2",
                    "accept-language": "ru",
                    "zoom": 18,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": "DTP Assistant local development",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return self._format_osm_address(data)

        except requests.RequestException as exc:
            self._log_request_error("OSM reverse geocoder", exc)
            return None

    @staticmethod
    def _format_yandex_address(geocoder_meta: dict) -> Optional[str]:
        address = geocoder_meta.get("Address", {})
        components = address.get("Components", [])

        by_kind = {}
        for component in components:
            kind = component.get("kind")
            name = component.get("name")
            if kind and name and kind not in by_kind:
                by_kind[kind] = name

        city = by_kind.get("locality")
        street = by_kind.get("street")
        house = by_kind.get("house")

        if street and house:
            street = f"{street}, {house}"

        parts = [part for part in [city, street] if part]
        if parts:
            return ", ".join(dict.fromkeys(parts))

        return geocoder_meta.get("text") or None

    @staticmethod
    def _format_osm_address(data: dict) -> Optional[str]:
        address = data.get("address", {})
        if not address:
            return data.get("display_name") or None

        road = address.get("road") or address.get("pedestrian") or address.get("footway")
        house_number = address.get("house_number")
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
        )
        street = road or address.get("neighbourhood")
        if street and house_number:
            street = f"{street}, {house_number}"

        parts = [part for part in [city, street] if part]
        if parts:
            return ", ".join(dict.fromkeys(parts))

        return data.get("display_name") or None

    @staticmethod
    def _log_request_error(service_name: str, exc: requests.RequestException) -> None:
        response = getattr(exc, "response", None)
        details = response.text[:300] if response is not None else ""
        print(f"{service_name} error: {exc}. {details}")


geocoder_service = YandexGeocoderService()
