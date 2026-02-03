from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import settings


@dataclass(frozen=True)
class BookingContext:
    booking_id: str
    property_id: str
    guest_last_name: str | None
    guest_language: str | None


class CiaoBookingClient:
    """
    Integrazione Ciao Booking.
    - In produzione: implementare chiamate reali alle API secondo la documentazione.
    - In test: MOCK_CIAO_BOOKING=true + data/mock_ciaobooking.json
    """

    def get_booking_by_phone(self, phone_e164: str) -> BookingContext | None:
        if settings.mock_ciao_booking:
            return self._mock_get_booking_by_phone(phone_e164)

        if not settings.ciao_booking_base_url:
            raise RuntimeError("CIAO_BOOKING_BASE_URL is missing.")

        # NOTE: placeholder: da sostituire con endpoint reali.
        # Esempio ipotetico:
        # GET /api/bookings?phone=...
        url = f"{settings.ciao_booking_base_url.rstrip('/')}/api/bookings"
        headers = {}
        if settings.ciao_booking_api_key:
            headers["Authorization"] = f"Bearer {settings.ciao_booking_api_key}"
        params = {"phone": phone_e164}

        with httpx.Client(timeout=settings.ciao_booking_timeout_s) as client:
            r = client.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()

        # Adatta questo parsing alla risposta reale.
        item = (data or {}).get("booking") if isinstance(data, dict) else None
        if not item:
            return None
        return BookingContext(
            booking_id=str(item.get("id", "")),
            property_id=str(item.get("property_id", "")),
            guest_last_name=(item.get("guest_last_name") or None),
            guest_language=(item.get("language") or None),
        )

    @staticmethod
    def _mock_get_booking_by_phone(phone_e164: str) -> BookingContext | None:
        path = Path("data/mock_ciaobooking.json")
        if not path.exists():
            return None
        blob = json.loads(path.read_text(encoding="utf-8"))
        items = blob.get("bookings", []) if isinstance(blob, dict) else []
        for b in items:
            if str(b.get("phone_e164", "")).strip() == phone_e164:
                return BookingContext(
                    booking_id=str(b.get("booking_id", "")),
                    property_id=str(b.get("property_id", "")),
                    guest_last_name=(b.get("guest_last_name") or None),
                    guest_language=(b.get("guest_language") or None),
                )
        return None

