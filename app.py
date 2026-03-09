from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas


RATES_FILE_CANDIDATES = ("rates.xlsx", "Rates.xlsx")
SERVICES_SHEET = "services"
HOTELS_SHEET = "hotels"


_rates_cache: tuple[pd.DataFrame, pd.DataFrame] | None = None


def _load_rates_file() -> Path:
    """Return the first existing rates file path from known candidates."""
    for filename in RATES_FILE_CANDIDATES:
        path = Path(filename)
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find rates workbook. Expected one of: "
        + ", ".join(RATES_FILE_CANDIDATES)
    )


def _normalize_text(value: str) -> str:
    return str(value).strip().lower()


def _normalize_month(value: str) -> str:
    return _normalize_text(value)


def _load_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load services and hotels tables from the workbook and normalize key columns."""
    global _rates_cache
    if _rates_cache is not None:
        return _rates_cache

    rates_file = _load_rates_file()

    services_df = pd.read_excel(rates_file, sheet_name=SERVICES_SHEET)
    hotels_df = pd.read_excel(rates_file, sheet_name=HOTELS_SHEET)

    services_df.columns = [str(c).strip().lower() for c in services_df.columns]
    hotels_df.columns = [str(c).strip().lower() for c in hotels_df.columns]

    required_services = {"service_type", "product", "month"}
    required_hotels = {"hotel", "room_type", "month"}

    if not required_services.issubset(services_df.columns):
        missing = required_services - set(services_df.columns)
        raise ValueError(f"Missing required services columns: {sorted(missing)}")

    if not required_hotels.issubset(hotels_df.columns):
        missing = required_hotels - set(hotels_df.columns)
        raise ValueError(f"Missing required hotels columns: {sorted(missing)}")

    services_df["product"] = services_df["product"].map(_normalize_text)
    services_df["month"] = services_df["month"].map(_normalize_month)

    hotels_df["hotel"] = hotels_df["hotel"].map(_normalize_text)
    hotels_df["room_type"] = hotels_df["room_type"].map(_normalize_text)
    hotels_df["month"] = hotels_df["month"].map(_normalize_month)

    _rates_cache = (services_df, hotels_df)
    return _rates_cache


def _pax_column(pax: int) -> str:
    if not isinstance(pax, int):
        raise TypeError("pax must be an integer")
    if pax < 1 or pax > 6:
        raise ValueError("pax must be between 1 and 6")
    return f"pax{pax}"


def get_service_price(product: str, month: str, pax: int) -> float:
    """Return unit service price for a product and month at a given pax level."""
    services_df, _ = _load_tables()
    pax_col = _pax_column(pax)

    if pax_col not in services_df.columns:
        raise ValueError(f"Column '{pax_col}' not found in services sheet")

    product_key = _normalize_text(product)
    month_key = _normalize_month(month)

    matches = services_df[
        (services_df["product"] == product_key) & (services_df["month"] == month_key)
    ]

    if matches.empty:
        raise ValueError(
            f"Service rate not found for product='{product}', month='{month}'"
        )

    price = matches.iloc[0][pax_col]
    return float(price)


def get_hotel_price(hotel: str, room_type: str, month: str, pax: int) -> float:
    """Return nightly hotel rate for a hotel/room/month at a given pax level."""
    _, hotels_df = _load_tables()
    pax_col = _pax_column(pax)

    if pax_col not in hotels_df.columns:
        raise ValueError(f"Column '{pax_col}' not found in hotels sheet")

    hotel_key = _normalize_text(hotel)
    room_key = _normalize_text(room_type)
    month_key = _normalize_month(month)

    matches = hotels_df[
        (hotels_df["hotel"] == hotel_key)
        & (hotels_df["room_type"] == room_key)
        & (hotels_df["month"] == month_key)
    ]

    if matches.empty:
        raise ValueError(
            "Hotel rate not found for "
            f"hotel='{hotel}', room_type='{room_type}', month='{month}'"
        )

    price = matches.iloc[0][pax_col]
    return float(price)


def calculate_quote(
    month: str,
    pax: int,
    nights: int,
    hotel: str,
    room: str,
    services_list: Iterable[str],
) -> float:
    """Calculate total package cost: hotel (nightly * nights) + all listed services."""
    if not isinstance(nights, int) or nights < 1:
        raise ValueError("nights must be a positive integer")

    hotel_nightly_rate = get_hotel_price(hotel=hotel, room_type=room, month=month, pax=pax)
    services_total = sum(get_service_price(s, month, pax) for s in services_list)

    total_cost = hotel_nightly_rate * nights + services_total
    return float(total_cost)


def generate_quotation_pdf(
    guest_name: str,
    destination: str,
    hotel: str,
    tours: str | Iterable[str],
    transfers: str | Iterable[str],
    total_package_cost: float,
    output_path: str | Path = "quotation.pdf",
) -> Path:
    """Generate a quotation PDF with package details and return the saved file path."""

    def _as_text(value: str | Iterable[str]) -> str:
        if isinstance(value, str):
            return value
        return ", ".join(str(item) for item in value)

    destination_text = str(destination)
    hotel_text = str(hotel)
    tours_text = _as_text(tours)
    transfers_text = _as_text(transfers)
    total_cost_text = f"{float(total_package_cost):,.2f}"

    target_path = Path(output_path)
    pdf = canvas.Canvas(str(target_path), pagesize=LETTER)

    y = 740
    line_gap = 30

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, 780, "Quotation")

    pdf.setFont("Helvetica", 12)
    rows = [
        ("Guest Name", guest_name),
        ("Destination", destination_text),
        ("Hotel", hotel_text),
        ("Tours", tours_text),
        ("Transfers", transfers_text),
        ("Total Package Cost", total_cost_text),
    ]

    for label, value in rows:
        pdf.drawString(72, y, f"{label}: {value}")
        y -= line_gap

    pdf.save()
    return target_path


if __name__ == "__main__":
    print("Module loaded. Import and call calculate_quote(...) in your application.")
