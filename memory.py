# memory.py — Умная память агентов: материалы и работы
# Хранит правки специалистов, дедуплицирует по ключу, без лимита
import json, os, hashlib

MEMORY_PATH = os.path.join(os.path.dirname(__file__), "agent_memory.json")


def _key(entry: dict) -> str:
    """Уникальный ключ записи для дедупликации."""
    parts = [
        entry.get("type", "material"),
        entry.get("name", "").lower().strip(),
        entry.get("unit", "").lower().strip(),
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:12]


def load_memory() -> dict:
    """Загружает всю память. Формат: {key: entry}"""
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_correction(
    name: str,
    unit: str,
    correction_type: str,  # "material" | "work"
    **kwargs
):
    """
    Сохраняет правку специалиста.
    При повторной правке того же материала/работы — ЗАМЕНЯЕТ старую запись.

    Примеры:
      save_correction("Саморез ТЕХ 3,5×16мм", "упак.", "material",
                      purchase_price=280, client_price=360)
      save_correction("Штукатурка гипсовая стена", "м²", "work",
                      price_per_unit=1150, norm_note="машинный способ")
    """
    from datetime import date as _date
    mem = load_memory()
    entry = {
        "type":  correction_type,
        "name":  name.strip(),
        "unit":  unit.strip(),
        "date":  str(_date.today()),
        **kwargs,
    }
    k = _key(entry)
    # Если запись уже есть — заменяем (не дублируем)
    mem[k] = entry
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return k


def get_memory_for_prompt(limit: int = 30) -> str:
    """
    Возвращает строку с памятью для вставки в промпт агента.
    Берёт последние `limit` записей (по дате).
    """
    mem = load_memory()
    if not mem:
        return ""
    # Сортируем по дате (новые первые)
    entries = sorted(mem.values(), key=lambda e: e.get("date", ""), reverse=True)[:limit]
    lines = ["НАШИ СТАНДАРТЫ И ПРОВЕРЕННЫЕ ЦЕНЫ (из предыдущих КП):"]
    for e in entries:
        if e["type"] == "material":
            pp = e.get("purchase_price", "?")
            cp = e.get("client_price", "?")
            lines.append(
                f"  • [МАТЕРИАЛ] {e['name']} ({e['unit']}): "
                f"закупка {pp} ₽, клиенту {cp} ₽"
            )
        else:
            p  = e.get("price_per_unit", "?")
            note = e.get("norm_note", "")
            lines.append(
                f"  • [РАБОТА] {e['name']} ({e['unit']}): "
                f"{p} ₽/{e['unit']} {('— ' + note) if note else ''}"
            )
    return "\n".join(lines)


def get_memory_list(limit: int = 30) -> list:
    """Возвращает список словарей для передачи в suggest_materials."""
    mem = load_memory()
    if not mem:
        return []
    return sorted(mem.values(), key=lambda e: e.get("date", ""), reverse=True)[:limit]
