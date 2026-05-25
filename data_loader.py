# data_loader.py
# Загрузка расценок: сначала Google Sheets, потом fallback на default_data.py

import streamlit as st
import pandas as pd
from default_data import WORK_ITEMS, SECTION_ORDER


@st.cache_data(ttl=300)  # кэш 5 минут
def load_data() -> list[dict]:
    """
    Возвращает список работ.
    Если в secrets задан SHEET_URL — читает из Google Sheets.
    Иначе — использует встроенную базу default_data.py.
    """
    sheet_url = st.secrets.get("SHEET_URL", None)

    if sheet_url:
        try:
            df = pd.read_csv(sheet_url)
            # Ожидаемые колонки: id, section, subsection, name, unit,
            #   price_work, mat_name, mat_unit, mat_norm, mat_price
            df["mat_norm"] = pd.to_numeric(df["mat_norm"], errors="coerce").fillna(0)
            df["mat_price"] = pd.to_numeric(df["mat_price"], errors="coerce").fillna(0)
            df["price_work"] = pd.to_numeric(df["price_work"], errors="coerce").fillna(0)
            # Заменяем NaN в строковых полях на None
            for col in ["mat_name", "mat_unit"]:
                df[col] = df[col].where(df[col].notna(), None)
            return df.to_dict("records")
        except Exception as e:
            st.warning(f"⚠️ Не удалось загрузить Google Sheets: {e}. Используется встроенная база.")

    return WORK_ITEMS


def get_sections(items: list[dict]) -> list[str]:
    """Возвращает разделы в нужном порядке."""
    seen = []
    for item in items:
        s = item["section"]
        if s not in seen:
            seen.append(s)
    # Сначала те, что в SECTION_ORDER, потом остальные
    ordered = [s for s in SECTION_ORDER if s in seen]
    ordered += [s for s in seen if s not in ordered]
    return ordered


def get_subsections(items: list[dict], section: str) -> list[str]:
    """Возвращает подразделы для раздела (в порядке первого появления)."""
    seen = []
    for item in items:
        if item["section"] == section:
            sub = item.get("subsection", "")
            if sub and sub not in seen:
                seen.append(sub)
    return seen


def get_items(items: list[dict], section: str, subsection: str) -> list[dict]:
    """Возвращает позиции для раздела/подраздела."""
    return [
        i for i in items
        if i["section"] == section and i.get("subsection", "") == subsection
    ]
