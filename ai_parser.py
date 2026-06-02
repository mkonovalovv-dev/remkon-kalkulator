# ai_parser.py — AI-разбор ТЗ/сметы и семантическое сопоставление со справочником
# v2.0: Claude batch semantic matching (вместо difflib)
import io, json, re, os
import streamlit as st


# ─── Извлечение текста из файла ───────────────────────────────────────────────

def extract_text_from_xlsx(file_bytes: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines = []
    for sh in wb.sheetnames:
        ws = wb[sh]
        for row in ws.iter_rows(values_only=True):
            vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if vals:
                lines.append("\t".join(vals))
    return "\n".join(lines)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n".join(parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    lines = []
    for p in doc.paragraphs:
        if p.text.strip():
            lines.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            # Убираем дубли из merged cells
            seen = set(); uniq = []
            for c in cells:
                if c not in seen:
                    seen.add(c); uniq.append(c)
            if uniq:
                lines.append("\t".join(uniq))
    return "\n".join(lines)


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    if ext in ("xlsx", "xls"):
        return extract_text_from_xlsx(file_bytes)
    elif ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    return ""


# ─── Шаг 1: Извлечение позиций из ТЗ ────────────────────────────────────────

EXTRACT_SYSTEM = """Ты — эксперт по строительным сметам и ТЗ (Россия).
Извлеки из документа список строительных РАБОТ (не материалов, не оборудования, не реквизитов).
Верни ТОЛЬКО JSON-массив без пояснений и markdown.
Формат каждого объекта:
{"idx": 0, "name": "Название работы на русском", "unit": "м²", "qty": 25.5}
Правила:
- Нормализуй единицы: "100 м2" → умножь qty×100 и пиши unit="м²"; "100 м" → unit="м.п."
- qty=null если объём не указан
- Исключай: заголовки разделов, итоговые строки, реквизиты, чистые материалы/оборудование
- Если одна позиция дублируется по помещениям — объединяй, суммируй qty"""

def extract_works_from_tz(text: str, api_key: str) -> list[dict]:
    """Шаг 1: Claude извлекает работы из текста ТЗ."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": f"Извлеки работы:\n\n{text[:14000]}"}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ─── Шаг 2: Семантическое сопоставление через Claude ────────────────────────

MATCH_SYSTEM = """Ты — эксперт по строительным работам (Россия).
Тебе дан СПРАВОЧНИК позиций (id → название) и список РАБОТ из ТЗ.
Для каждой работы из ТЗ:
- Найди наиболее близкую позицию справочника по смыслу (не по буквам!)
- Если подходящей нет — matched_id = null
Верни ТОЛЬКО JSON-массив без пояснений:
[{"tz_idx": 0, "matched_id": "id_из_справочника_или_null", "confidence": 0.95, "comment": "кратко"}]
Confidence: 1.0 = точное соответствие, 0.7+ = очень близко, 0.4–0.7 = похоже, <0.4 = сомнительно, 0 = нет совпадения."""

def semantic_match(parsed: list[dict], all_items: list, api_key: str) -> list[dict]:
    """Шаг 2: Claude семантически сопоставляет работы с позициями справочника.
    Один батч-вызов на весь список."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Строим компактный каталог: id → name (только работы, без материалов)
    catalog_lines = [f"{item['id']}: {item['name']} [{item['section']}]"
                     for item in all_items]
    catalog_text = "\n".join(catalog_lines)

    tz_lines = [f"{p['idx']}: {p['name']} ({p['unit']})" for p in parsed]
    tz_text = "\n".join(tz_lines)

    # Если каталог слишком большой — разбиваем на батчи по 50 ТЗ-позиций
    BATCH_SIZE = 40
    all_results = []

    for batch_start in range(0, len(parsed), BATCH_SIZE):
        batch = parsed[batch_start:batch_start + BATCH_SIZE]
        batch_lines = [f"{p['idx']}: {p['name']} ({p['unit']})" for p in batch]
        batch_text  = "\n".join(batch_lines)

        prompt = (
            f"СПРАВОЧНИК ({len(all_items)} позиций):\n{catalog_text}\n\n"
            f"РАБОТЫ ИЗ ТЗ:\n{batch_text}"
        )

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=MATCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        all_results.extend(json.loads(raw))

    # Собираем финальный результат
    item_map = {i["id"]: i for i in all_items}
    results = []
    match_map = {r["tz_idx"]: r for r in all_results}

    for p in parsed:
        match_info = match_map.get(p["idx"], {})
        matched_id = match_info.get("matched_id")
        confidence = float(match_info.get("confidence", 0.0))
        comment    = match_info.get("comment", "")
        matched_item = item_map.get(matched_id) if matched_id else None

        results.append({
            "parsed_name":  p["name"],
            "parsed_unit":  p["unit"],
            "qty":          p.get("qty"),
            "matched_item": matched_item,
            "matched_id":   matched_id,
            "confidence":   round(confidence, 2),
            "comment":      comment,
            "in_catalog":   matched_item is not None,
        })

    return results


# ─── Совместимый wrapper (для обратной совместимости с app.py) ───────────────

def call_claude_api(text: str, api_key: str) -> list[dict]:
    """Извлекает позиции из текста ТЗ. Возвращает [{idx, name, unit, qty}]."""
    return extract_works_from_tz(text, api_key)


def match_items(parsed: list[dict], all_items: list, api_key: str = None) -> list[dict]:
    """Семантически сопоставляет позиции ТЗ со справочником через Claude.
    Принимает 2 или 3 аргумента — api_key необязателен, берётся из secrets/env автоматически."""
    if not api_key:
        try:
            import streamlit as _st
            api_key = _st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            return semantic_match(parsed, all_items, api_key)
        except Exception as e:
            # Fallback на difflib если что-то пошло не так
            pass

    # Fallback: difflib (старый способ, если нет ключа)
    import difflib
    names_lower = [i["name"].lower() for i in all_items]
    results = []
    for p in parsed:
        name_low = p.get("name", "").lower()
        matches  = difflib.get_close_matches(name_low, names_lower, n=1, cutoff=0.35)
        best_item = None
        score = 0.0
        if matches:
            idx = names_lower.index(matches[0])
            best_item = all_items[idx]
            score = difflib.SequenceMatcher(None, name_low, matches[0]).ratio()
        results.append({
            "parsed_name":  p.get("name", ""),
            "parsed_unit":  p.get("unit", ""),
            "qty":          p.get("qty"),
            "matched_item": best_item,
            "matched_id":   best_item["id"] if best_item else None,
            "confidence":   round(score, 2),
            "comment":      "difflib fallback",
            "in_catalog":   best_item is not None,
        })
    return results


# ─── Рыночные цены через Gemini ──────────────────────────────────────────────

def get_market_price(work_name: str, unit: str, gemini_key: str) -> dict:
    """Запрашивает у Gemini рыночную цену на работу в Москве.
    Возвращает {"price_min": int, "price_max": int, "price_mid": int, "source": str}"""
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        f"Найди рыночную стоимость строительной работы в Москве (2024-2025 год):\n"
        f"Работа: {work_name}\nЕдиница: {unit}\n\n"
        f"Ответь ТОЛЬКО JSON без пояснений:\n"
        f'{{\"price_min\": 500, \"price_max\": 1200, \"price_mid\": 850, \"source\": \"откуда данные\"}}'
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return {
            "price_min": int(data.get("price_min", 0)),
            "price_max": int(data.get("price_max", 0)),
            "price_mid": int(data.get("price_mid", 0)),
            "source":    data.get("source", "Gemini"),
        }
    except Exception as e:
        return {"price_min": 0, "price_max": 0, "price_mid": 0, "source": f"ошибка: {e}"}


# ─── Сохранение новой позиции в справочник ───────────────────────────────────

def save_to_catalog(name: str, unit: str, price: int, section: str,
                    subsection: str = "Из ТЗ") -> dict:
    """Создаёт новую позицию и добавляет её в default_data.py.
    Возвращает созданный item dict."""
    import uuid as _uuid

    new_id = f"learned_{_uuid.uuid4().hex[:8]}"
    new_item = {
        "id":         new_id,
        "section":    section,
        "subsection": subsection,
        "name":       name.strip(),
        "unit":       unit.strip() or "шт.",
        "works": [{"name": name.strip(), "unit": unit.strip() or "шт.",
                   "price": int(price), "norm": 1.0}],
        "materials": [],
    }

    # Дописываем в default_data.py
    catalog_path = os.path.join(os.path.dirname(__file__), "default_data.py")
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            content = f.read()

        last_bracket = content.rfind("\n]")
        if last_bracket != -1:
            entry = (
                f"\n    # ═══ Добавлено из ТЗ ═══\n"
                f"    {{\n"
                f'        "id": {repr(new_id)},\n'
                f'        "section": {repr(section)},\n'
                f'        "subsection": {repr(subsection)},\n'
                f'        "name": {repr(name.strip())},\n'
                f'        "unit": {repr(unit.strip() or "шт.")},\n'
                f'        "works": [{{"name": {repr(name.strip())}, "unit": {repr(unit.strip() or "шт.")}, "price": {int(price)}, "norm": 1.0}}],\n'
                f'        "materials": [],\n'
                f'    }},\n'
            )
            new_content = content[:last_bracket] + entry + "\n]"
            with open(catalog_path, "w", encoding="utf-8") as f:
                f.write(new_content)
    except Exception:
        pass  # Не удалось записать — работаем только через session_state

    return new_item


# ─── Повторная обработка с правками человека ─────────────────────────────────

REPROCESS_SYSTEM = """Ты — опытный сметчик (Россия, Москва, 2026 год).
Тебе дан состав КП после первичного AI-разбора ТЗ и ПРАВКИ менеджера.
Твоя задача — применить все правки и вернуть обновлённый список позиций.

Правила:
- "не включать" / "убрать" / "исключить" → status = "removed"
- "изменить объём" / "поменять количество" → status = "modified", обнови qty
- "добавить X" / "включить Y" → найди в справочнике или создай новую позицию, status = "added"
- Если позиция не изменилась → status = "unchanged"
- Раздел-комментарий: найди в справочнике все упомянутые работы и добавь их

Дата расчёта: 02.06.2026. Расчёт по безналичному расчёту с НДС 22%.

Верни ТОЛЬКО JSON-массив без пояснений:
[
  {
    "idx": 0,
    "name": "Название работы",
    "unit": "м²",
    "qty": 170.0,
    "matched_id": "id_из_справочника_или_null",
    "status": "unchanged|modified|added|removed",
    "change_note": "Краткое описание что изменилось (только для modified/added/removed)"
  }
]"""


def reprocess_with_edits(
    positions: list[dict],
    section_comments: dict[str, str],
    all_items: list,
    api_key: str,
) -> list[dict]:
    """
    Применяет правки менеджера к составу КП через Claude.

    positions: список dict с полями idx, name, unit, qty, matched_id, status_human, comment
    section_comments: {section_name: "текст правки по разделу"}
    all_items: справочник позиций
    Возвращает обновлённый список с полем status: unchanged|modified|added|removed
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Собираем текст правок
    edits_lines = []
    for p in positions:
        comment = (p.get("comment") or "").strip()
        include = p.get("include", True)
        if not include:
            edits_lines.append(f"Позиция {p['idx']} ({p['name']}): НЕ ВКЛЮЧАТЬ")
        elif comment:
            edits_lines.append(f"Позиция {p['idx']} ({p['name']}): {comment}")

    for section, comment in section_comments.items():
        if comment and comment.strip():
            edits_lines.append(f"По разделу «{section}»: {comment.strip()}")

    if not edits_lines:
        # Нет правок — возвращаем как есть с status=unchanged
        return [
            {**p, "status": "unchanged", "change_note": ""}
            for p in positions
        ]

    edits_text = "\n".join(edits_lines)

    # Исходный состав
    pos_lines = []
    for p in positions:
        mid = p.get("matched_id", "—")
        pos_lines.append(
            f"{p['idx']}. {p['name']} | {p.get('qty', '?')} {p.get('unit', '')} "
            f"| matched_id: {mid}"
        )
    positions_text = "\n".join(pos_lines)

    # Компактный справочник
    catalog_text = "\n".join(
        f"{item['id']}: {item['name']} [{item['section']}] {item['unit']}"
        for item in all_items
    )

    prompt = (
        f"ИСХОДНЫЙ СОСТАВ КП:\n{positions_text}\n\n"
        f"ПРАВКИ МЕНЕДЖЕРА:\n{edits_text}\n\n"
        f"СПРАВОЧНИК ПОЗИЦИЙ:\n{catalog_text[:8000]}"
    )

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=REPROCESS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        updated = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: механически применяем правки
        updated = []
        exclude_ids = {p["idx"] for p in positions if not p.get("include", True)}
        for p in positions:
            status = "removed" if p["idx"] in exclude_ids else "unchanged"
            updated.append({**p, "status": status, "change_note": ""})
        return updated

    # Обогащаем matched_item из справочника
    item_map = {i["id"]: i for i in all_items}
    for row in updated:
        mid = row.get("matched_id")
        row["matched_item"] = item_map.get(mid) if mid else None

    return updated
