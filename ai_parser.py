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

EXTRACT_SYSTEM = """Ты — Сергей Николаевич, технический эксперт с красными дипломами трёх строительных вузов
(МГСУ, НИУ МГСУ, СПбГАСУ) и 30-летним стажем главного прораба на объектах любой сложности:
жилые дома, торговые центры, промышленные здания, аэропорты, исторические реставрации.

Ты читаешь технические задания глубоко — не как переписчик, а как профессионал который
понимает строительную технологию, последовательность работ, взаимосвязи между позициями.

ТВОЯ ЗАДАЧА: из ТЗ/сметы/описания извлечь ПОЛНЫЙ и ПРАВИЛЬНЫЙ перечень работ.

ПРИНЦИПЫ РАБОТЫ:
1. Читай документ ЦЕЛИКОМ, осмысливая контекст. Одна фраза может содержать 3-5 работ.
2. Понимай технологические цепочки: "монтаж перегородок из ГКЛ" → это каркас + листы + шпаклёвка стыков.
3. Извлекай явные И подразумеваемые работы (если написано "установить дверь" — значит нужна подготовка проёма и наличники).
4. Если в тексте указаны размеры (длина, площадь, высота, количество) — ИСПОЛЬЗУЙ их для расчёта объёма.
5. Если тот же вид работы упоминается для нескольких помещений — СУММИРУЙ или создай отдельные строки с пометкой.
6. Нормализуй единицы: "100 м2" → qty×100, unit="м²"; "100 м" → unit="м.п."; "10 шт" → unit="шт."
7. Не пропускай ничего — за каждой строкой ТЗ может стоять работа.

ЧТО ИЗВЛЕКАТЬ:
✓ Все монтажные, демонтажные, отделочные, инженерные работы
✓ Подготовительные работы (очистка, разметка, грунтовка)
✓ Вспомогательные работы (защитные мероприятия, вывоз мусора)
✓ Работы по каждому помещению если они различаются
✓ Работы которые ПОДРАЗУМЕВАЮТСЯ технологией но прямо не написаны

ЧТО НЕ ИЗВЛЕКАТЬ:
✗ Реквизиты сторон, подписи, даты договора
✗ Требования к документации (ППР, акты, журналы)
✗ Условия оплаты и гарантийные обязательства
✗ Перечни представляемых документов

Верни ТОЛЬКО JSON-массив без пояснений и markdown:
[
  {"idx": 0, "name": "Чёткое название работы на русском", "unit": "м²", "qty": 25.5},
  ...
]

qty=null ТОЛЬКО если объём невозможно определить из контекста.
Названия работ — конкретные, профессиональные, понятные сметчику."""

def extract_works_from_tz(text: str, api_key: str) -> list[dict]:
    """Шаг 1: Claude извлекает работы из текста ТЗ."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
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
    """
    Ищет ОПТОВУЮ закупочную цену через Gemini у специализированных поставщиков.
    Логика: price_mid = наша закупочная. client_price = price_mid × 1.3-1.4.
    Клиент гуглит Петрович → видит дороже или столько же → доволен.
    """
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        f"Найди ОПТОВУЮ закупочную цену на товар/материал в Москве (2025-2026).\n"
        f"Товар: {work_name}\nЕдиница: {unit}\n\n"
        f"Ищи у специализированных оптовиков и дистрибьюторов — НЕ в розничных магазинах:\n"
        f"• Сантехника: Таваго, Valtec, Хит Сантехника, ВодоградМ\n"
        f"• Электрика: Сатурн, ЭТМ, АБС Электро, Русский Свет\n"
        f"• ГКЛ / смеси: официальные дистрибьюторы Кнауф, Церезит, Волма\n"
        f"• Металл / профиль: Металлсервис, Брок-Инвест, ТПК\n"
        f"• Общестрой: оптовые строительные базы Москвы\n\n"
        f"Розничные магазины (Петрович, Леруа, OBI, Строймастер) — НЕ использовать.\n"
        f"Нужна реальная цена по которой строительная компания закупает оптом.\n\n"
        f"Ответь ТОЛЬКО JSON без пояснений:\n"
        f'{{\"price_min\": 400, \"price_max\": 700, \"price_mid\": 550, \"source\": \"Таваго / ЭТМ\"}}'
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        json_m = re.search(r"\{[\s\S]*?\}", raw)
        if json_m:
            raw = json_m.group()
        data = json.loads(raw)
        return {
            "price_min": int(data.get("price_min", 0)),
            "price_max": int(data.get("price_max", 0)),
            "price_mid": int(data.get("price_mid", 0)),
            "source":    data.get("source", "оптовый поставщик"),
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
        comment = (p.get("user_comment") or "").strip()  # правка менеджера
        include = p.get("include", True)
        if not include:
            edits_lines.append(f"Позиция {p['idx']} ({p.get('parsed_name', p.get('name', '?'))}): НЕ ВКЛЮЧАТЬ")
        elif comment:
            edits_lines.append(f"Позиция {p['idx']} ({p.get('parsed_name', p.get('name', '?'))}): {comment}")

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
        pname = p.get('parsed_name', p.get('name', '?'))
        punit = p.get('parsed_unit', p.get('unit', ''))
        pos_lines.append(
            f"{p['idx']}. {pname} | {p.get('qty', '?')} {punit} "
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

    # Обогащаем matched_item из справочника + нормализуем ключи
    # Claude возвращает "name"/"unit", но display-код ждёт "parsed_name"/"parsed_unit"
    item_map = {i["id"]: i for i in all_items}
    # Строим маппинг idx → исходная позиция (для fallback parsed_name)
    orig_by_idx = {p.get("idx", i): p for i, p in enumerate(positions)}

    for row in updated:
        mid = row.get("matched_id")
        row["matched_item"] = item_map.get(mid) if mid else None
        # Нормализация: если нет parsed_name — берём из name или из исходной позиции
        if not row.get("parsed_name"):
            orig = orig_by_idx.get(row.get("idx", -1), {})
            row["parsed_name"] = (row.get("name")
                                  or orig.get("parsed_name")
                                  or orig.get("name", "?"))
        if not row.get("parsed_unit"):
            orig = orig_by_idx.get(row.get("idx", -1), {})
            row["parsed_unit"] = (row.get("unit")
                                  or orig.get("parsed_unit")
                                  or orig.get("unit", "ед."))
        # Гарантируем наличие include и user_comment для повторного редактирования
        if "include" not in row:
            row["include"] = row.get("status", "unchanged") != "removed"
        if "user_comment" not in row:
            row["user_comment"] = ""
        if "in_catalog" not in row:
            row["in_catalog"] = row.get("matched_item") is not None

    return updated


# ─── Шаг 3: Детальная разбивка работ на подработы и материалы ────────────────

EXPAND_SYSTEM = """Ты — Сергей Николаевич, главный прораб с 30-летним стажем и тремя строительными дипломами.

ГЛАВНЫЙ ПРИНЦИП — КОНЕЧНЫЙ ПРОДУКТ:
Любая работа в КП — это готовый результат который принимает заказчик.
- "Установка двери" = дверь открывается и закрывается (с петлями, замком, наличниками, пеной)
- "Укладка плитки" = пол по которому можно ходить (с клеем, нарезкой, затиркой)
- "Монтаж светильника" = он светит (с подключением к электрике)
- "Штукатурка стен" = ровные стены под покраску (с маяками, грунтовкой, заделкой маяков)
- "ГКЛ-перегородка" = стоит и держит (с каркасом, листами, армированием, шпаклёвкой стыков)
Никогда не выдавай компонентные позиции когда нужен готовый комплексный продукт.

Для каждой работы составь ПОЛНУЮ разбивку в технологической последовательности.

УНИВЕРСАЛЬНЫЕ ПРАВИЛА ПРО МАТЕРИАЛЫ:
- Округляй В БОЛЬШУЮ СТОРОНУ до целой упаковки (9.5 шт → 10 шт, 2.3 мешка → 3 мешка)
- Запас: 10% на профили/погонаж, 5% на листовые и хрупкие, 3-5% на смеси
- Включай ВЕСЬ крепёж: дюбели, саморезы, анкеры (2 дюбеля на подвес × N подвесов)
- Включай расходники: перчатки, маски, плёнка защитная, мешки для мусора
- Инструмент разового использования (шпатели, валики, кисти) — включать

ТЕХНОЛОГИЧЕСКИЕ ЦЕПОЧКИ:
Штукатурка → грунтовка основания + адгезионный слой + установка маяков + штукатурка + демонтаж маяков + заделка следов
ГКЛ-перегородка → разметка + направляющие UW + стойки CD шаг 600мм + обшивка + армирование серпянкой + шпаклёвка стыков
Плитка пол → подготовка + гидроизоляция (если С/У) + клей + укладка + нарезка + затирка
Плитка стены → грунтовка + клей + укладка + нарезка + затирка
Потолок Armstrong/Clip-in → разметка + пристенный профиль + несущие + поперечины + кассеты
Потолок грильято/реечный → разметка + пристенный профиль + каркас + модули + ПОКРАСКА ВИДИМОЙ ЧАСТИ ПОТОЛКА в цвет (через ячейки виден потолок → грунт + краска видимой части, НЕ чистить весь потолок)
Дверь → подготовка проёма + установка коробки + запенивание + навешивание полотна + петли + замок + ручка + наличники + добор
Стяжка → очистка + бетоноконтакт + маяки + стяжка + выравнивание + затирка + уход 3 дня
Окна ПВХ → демонтаж старого + монтаж рамы + пена + подоконник + откосы + отлив
Электрика розетки → штроба + гофра + кабель + подрозетник + соединения + механизм + рамка

СВЯЗАННЫЕ РАЗДЕЛЫ (добавлять в related_sections):
- Подвесной потолок → "💡 Рекомендуем: монтаж светильников/освещение"
- Стяжка → "⬛ Рекомендуем: финишное покрытие (ламинат/кварцвинил/плитка)"
- ГКЛ-перегородки → "🎨 Рекомендуем: малярные работы по ГКЛ"
- Санузел → "🚿 Рекомендуем: гидроизоляцию перед плиткой"

Верни ТОЛЬКО JSON без пояснений:
[
  {
    "idx": 0,
    "name": "Исходная работа из ТЗ",
    "unit": "м²",
    "qty": 100.0,
    "sub_works": [
      {"name": "Разметка осей", "unit": "м²", "qty_per_unit": 1.0, "note": ""},
      {"name": "Грунтовка потолка", "unit": "м²", "qty_per_unit": 1.0, "note": "1 слой"}
    ],
    "materials": [
      {
        "name": "Грунтовка Knauf Tiefengrund 10л",
        "unit": "канистра 10л",
        "qty_raw": 15.0,
        "qty_order": 20.0,
        "pack_size": 10.0,
        "note": "расход 0.15л/м², 2 канистры"
      }
    ],
    "related_sections": ["💡 Рекомендуем: монтаж светильников"]
  }
]"""


def expand_works_with_details(
    positions: list[dict],
    api_key: str,
    progress_callback=None,
) -> list[dict]:
    """
    Шаг 3: Детальная разбивка каждой позиции на подработы + материалы.
    Работает батчами по 10 позиций чтобы не перегружать контекст.
    progress_callback(step, total, msg) — опциональный колбэк для прогресс-бара.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    BATCH = 8  # позиций за один вызов
    all_results = []

    for batch_start in range(0, len(positions), BATCH):
        batch = positions[batch_start:batch_start + BATCH]

        if progress_callback:
            step = batch_start // BATCH + 1
            total = (len(positions) + BATCH - 1) // BATCH
            names = ", ".join(p.get("name", "?")[:25] for p in batch[:2])
            progress_callback(step, total, f"Разбиваю: {names}…")

        # Компактное описание батча
        batch_text = "\n".join(
            f"{p['idx']}: {p.get('name','?')} | {p.get('qty','?')} {p.get('unit','?')}"
            for p in batch
        )

        try:
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8000,
                system=EXPAND_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Сделай детальную разбивку для этих {len(batch)} позиций:\n\n"
                        f"{batch_text}"
                    )
                }],
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"^```\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            # Вытаскиваем JSON массив
            arr_m = re.search(r"\[[\s\S]*\]", raw)
            if arr_m:
                raw = arr_m.group()
            batch_result = json.loads(raw)
            all_results.extend(batch_result)
        except Exception as e:
            # Если батч упал — добавляем позиции без разбивки
            for p in batch:
                all_results.append({
                    "idx": p.get("idx", 0),
                    "name": p.get("name", ""),
                    "unit": p.get("unit", ""),
                    "qty": p.get("qty"),
                    "sub_works": [],
                    "materials": [],
                    "expand_error": str(e),
                })

    return all_results


# ─── Мониторинг рыночных цен на РАБОТЫ ──────────────────────────────────────

def get_work_market_price(work_name: str, unit: str, gemini_key: str) -> dict:
    """
    Ищет рыночную КЛИЕНТСКУЮ цену на строительную работу.
    Принцип конечного продукта: дверь = открывается, плитка = можно ходить.
    Семантический поиск: "установка" = "монтаж" = "укладка".
    Сравнивает только комплексные цены, отфильтровывает компонентные.
    Возвращает {"price_min", "price_max", "price_mid", "source", "what_included", "warning"}
    """
    import google.generativeai as genai
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = (
        f"Найди рыночную стоимость строительной работы в Москве (2025-2026).\n"
        f"Работа: {work_name}\nЕдиница: {unit}\n\n"
        f"ВАЖНО — ПРИНЦИП КОНЕЧНОГО ПРОДУКТА:\n"
        f"Ищи КОМПЛЕКСНУЮ цену за готовый результат. Примеры:\n"
        f"- 'Установка двери' = дверь открывается (с петлями, замком, наличниками, пеной) — не отдельно каждый элемент\n"
        f"- 'Укладка плитки' = пол по которому ходят (с клеем, нарезкой, затиркой) — не отдельно клей и затирка\n"
        f"- 'Штукатурка' = ровные стены (с маяками, грунтовкой, заделкой) — не отдельно маяки\n\n"
        f"СЕМАНТИЧЕСКИЙ ПОИСК:\n"
        f"'Установка' = 'монтаж' = 'укладка' для одного типа работы.\n"
        f"Ищи по смыслу, не по точному названию.\n\n"
        f"ИСТОЧНИКИ: Яндекс.Услуги, Авито (прайсы компаний), Remontik.org, 2ГИС, сайты строительных компаний.\n"
        f"НЕ смотри цены физлиц-мастеров — только подрядные организации.\n"
        f"Если видишь компонентные цены (отдельно каждая мелочь) — ИГНОРИРУЙ их.\n\n"
        f"Сравни минимум 3 источника. Объясни что входит в цену.\n\n"
        f"Ответь ТОЛЬКО JSON без пояснений:\n"
        f'{{\"price_min\": 500, \"price_max\": 1200, \"price_mid\": 850, '
        f'\"source\": \"Яндекс.Услуги, Авито\", '
        f'\"what_included\": \"что входит в комплексную цену\", '
        f'\"warning\": \"хитрости или подводные камни если есть или null\"}}'
    )

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        json_m = re.search(r"\{[\s\S]*?\}", raw)
        if json_m:
            raw = json_m.group()
        data = json.loads(raw)
        return {
            "price_min":     int(data.get("price_min", 0)),
            "price_max":     int(data.get("price_max", 0)),
            "price_mid":     int(data.get("price_mid", 0)),
            "source":        data.get("source", "рынок"),
            "what_included": data.get("what_included", ""),
            "warning":       data.get("warning"),
        }
    except Exception as e:
        return {"price_min": 0, "price_max": 0, "price_mid": 0, "source": f"ошибка: {e}",
                "what_included": "", "warning": None}
