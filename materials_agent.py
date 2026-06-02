# materials_agent.py — Разговорный агент подбора материалов
# Claude помогает выбрать материалы по норме расхода, предлагает варианты,
# переспрашивает если что-то неясно.
import json, re

# ─── Расширенный каталог материалов с вариантами ─────────────────────────────
# Структура:
# {
#   "material_key": {
#     "name": "Штукатурка гипсовая",
#     "unit": "меш. 30кг",
#     "variants": {
#       "эконом":    {"brand": "...", "purchase": 450, "client": 620},
#       "стандарт":  {"brand": "...", "purchase": 850, "client": 1050},
#       "премиум":   {"brand": "...", "purchase": 1100, "client": 1350},
#     },
#     "clarifying": ["Будет ли армирующая сетка?", "..."],  # вопросы если нужны
#   }
# }

MATERIAL_CATALOG: dict[str, dict] = {
    "штукатурка_гипсовая": {
        "name": "Штукатурка гипсовая",
        "unit": "меш. 30кг",
        "variants": {
            "эконом":   {"brand": "Волма Штукатурка 30кг",       "purchase": 430, "client": 580},
            "стандарт": {"brand": "Knauf Rotband 30кг",           "purchase": 850, "client": 1050},
            "премиум":  {"brand": "Bergauf Bau Interier 30кг",    "purchase": 980, "client": 1250},
        },
    },
    "штукатурка_цпс": {
        "name": "Штукатурка цементно-песчаная",
        "unit": "меш. 25кг",
        "variants": {
            "эконом":   {"brand": "ЦПС М150 25кг (ТД Цемент)",   "purchase": 280, "client": 380},
            "стандарт": {"brand": "Knauf Unterputz 25кг",          "purchase": 520, "client": 680},
            "премиум":  {"brand": "Mapei Maplatherm 25кг",         "purchase": 780, "client": 990},
        },
    },
    "клей_для_плитки": {
        "name": "Клей для плитки",
        "unit": "меш. 25кг",
        "variants": {
            "эконом":   {"brand": "Геркулес ГМ-11 25кг",          "purchase": 280, "client": 380},
            "стандарт": {"brand": "Knauf Flexkleber 25кг",         "purchase": 520, "client": 680},
            "премиум":  {"brand": "Litokol X11 25кг",              "purchase": 780, "client": 1020},
        },
    },
    "гкл_стандарт": {
        "name": "Лист ГКЛ стандартный 12,5мм",
        "unit": "лист 1200×2500",
        "variants": {
            "эконом":   {"brand": "Гипрок Стандарт 12,5мм",       "purchase": 520, "client": 680},
            "стандарт": {"brand": "Knauf ГКЛ 12,5мм",             "purchase": 680, "client": 890},
            "премиум":  {"brand": "Knauf Сапфир 12,5мм",          "purchase": 820, "client": 1050},
        },
    },
    "гкл_влагостойкий": {
        "name": "Лист ГКЛВ влагостойкий 12,5мм",
        "unit": "лист 1200×2500",
        "variants": {
            "эконом":   {"brand": "Гипрок Аква 12,5мм",           "purchase": 680, "client": 880},
            "стандарт": {"brand": "Knauf ГКЛВ 12,5мм",            "purchase": 820, "client": 1050},
            "премиум":  {"brand": "Knauf Аква 12,5мм",            "purchase": 950, "client": 1200},
        },
    },
    "профиль_cd": {
        "name": "Профиль CD 60×27мм 3м",
        "unit": "шт.",
        "variants": {
            "эконом":   {"brand": "Профиль CD 0,45мм 3м",         "purchase": 75,  "client": 110},
            "стандарт": {"brand": "Knauf CD 0,55мм 3м",           "purchase": 110, "client": 155},
            "премиум":  {"brand": "Knauf CD 0,6мм 3м",            "purchase": 135, "client": 185},
        },
    },
    "профиль_uw": {
        "name": "Профиль UW 75×40мм 3м",
        "unit": "шт.",
        "variants": {
            "эконом":   {"brand": "Профиль UW 0,45мм 3м",         "purchase": 80,  "client": 115},
            "стандарт": {"brand": "Knauf UW 0,55мм 3м",           "purchase": 120, "client": 165},
            "премиум":  {"brand": "Knauf UW 0,6мм 3м",            "purchase": 145, "client": 195},
        },
    },
    "шпаклевка_финишная": {
        "name": "Шпаклёвка финишная",
        "unit": "меш. 25кг",
        "variants": {
            "эконом":   {"brand": "Волма Финиш 25кг",             "purchase": 380, "client": 520},
            "стандарт": {"brand": "Knauf Финишная 25кг",          "purchase": 580, "client": 760},
            "премиум":  {"brand": "Danogips SuperFinish 28кг",    "purchase": 750, "client": 980},
        },
    },
    "грунтовка": {
        "name": "Грунтовка универсальная",
        "unit": "л",
        "variants": {
            "эконом":   {"brand": "Старатели Грунт 10л",          "purchase": 290, "client": 390},
            "стандарт": {"brand": "Knauf Tiefengrund 10л",        "purchase": 480, "client": 640},
            "премиум":  {"brand": "Ceresit CT 17 10л",            "purchase": 680, "client": 880},
        },
    },
    "краска_интерьерная": {
        "name": "Краска интерьерная белая",
        "unit": "вед. 10л",
        "variants": {
            "эконом":   {"brand": "Olecolor Интерьерная 10л",     "purchase": 780, "client": 1050},
            "стандарт": {"brand": "Dulux Bindo 7 10л",            "purchase": 1650,"client": 2100},
            "премиум":  {"brand": "Tikkurila Joker 10л",          "purchase": 2800,"client": 3500},
        },
    },
    "бетоноконтакт": {
        "name": "Бетоноконтакт (грунтовка адгезионная)",
        "unit": "вед. 20кг",
        "variants": {
            "эконом":   {"brand": "Старатели Бетоноконтакт 20кг","purchase": 580, "client": 780},
            "стандарт": {"brand": "Knauf Betokontakt 20кг",       "purchase": 1850,"client": 2350},
            "премиум":  {"brand": "Ceresit CT 19 15кг",           "purchase": 2200,"client": 2800},
        },
    },
    "стяжка_цпс": {
        "name": "Смесь для стяжки ЦПС М150",
        "unit": "меш. 25кг",
        "variants": {
            "эконом":   {"brand": "ЦПС М150 25кг (местн.)",       "purchase": 280, "client": 380},
            "стандарт": {"brand": "Knauf Triolit 25кг",           "purchase": 450, "client": 600},
            "премиум":  {"brand": "Litokol Litolast 25кг",        "purchase": 650, "client": 850},
        },
    },
    "газоблок": {
        "name": "Газобетонный блок D500",
        "unit": "м³",
        "variants": {
            "эконом":   {"brand": "Ytong D500 625×250×200мм",     "purchase": 6800, "client": 8800},
            "стандарт": {"brand": "Bonolit D500 625×250×200мм",   "purchase": 7200, "client": 9400},
            "премиум":  {"brand": "H+H D500 625×300×200мм",       "purchase": 8500, "client": 11000},
        },
    },
    "клей_для_блоков": {
        "name": "Клей для газоблоков",
        "unit": "меш. 25кг",
        "variants": {
            "эконом":   {"brand": "Геркулес Газобетон 25кг",      "purchase": 280, "client": 380},
            "стандарт": {"brand": "Ytong D1 25кг",                "purchase": 450, "client": 590},
            "премиум":  {"brand": "Bonolit Клей зимний 25кг",     "purchase": 550, "client": 720},
        },
    },
    "гидроизоляция": {
        "name": "Гидроизоляция обмазочная",
        "unit": "кг",
        "variants": {
            "эконом":   {"brand": "Технониколь Технофлекс 20кг",  "purchase": 85,  "client": 120},
            "стандарт": {"brand": "Knauf Флехендихт 20кг",        "purchase": 145, "client": 195},
            "премиум":  {"brand": "Litokol Coverflex 20кг",       "purchase": 220, "client": 290},
        },
    },
    "затирка_цементная": {
        "name": "Затирка цементная",
        "unit": "меш. 2кг",
        "variants": {
            "эконом":   {"brand": "Геркулес Затирка 2кг",         "purchase": 85,  "client": 120},
            "стандарт": {"brand": "Ceresit CE 33 2кг",            "purchase": 145, "client": 195},
            "премиум":  {"brand": "Litokol Litochrom 2кг",        "purchase": 220, "client": 295},
        },
    },
    "затирка_эпоксидная": {
        "name": "Затирка эпоксидная",
        "unit": "компл. 2кг",
        "variants": {
            "эконом":   {"brand": "Mapei Kerapoxy Design 2кг",    "purchase": 1200,"client": 1600},
            "стандарт": {"brand": "Litokol Starlike 2,5кг",       "purchase": 2100,"client": 2800},
            "премиум":  {"brand": "Litokol Starlike Evo 2,5кг",   "purchase": 2800,"client": 3700},
        },
    },
}

DEFAULT_MARKUP_PCT = 20  # % наценки на закупочную цену по умолчанию


def get_client_price(purchase_price: float, markup_pct: float = DEFAULT_MARKUP_PCT) -> int:
    """Рассчитывает цену для клиента с наценкой."""
    return int(purchase_price * (1 + markup_pct / 100))


# ─── Промпт для материального агента ─────────────────────────────────────────

MATERIALS_AGENT_SYSTEM = """Ты — Палыч, прораб-снабженец с 35 годами за плечами. Москва, стройки всякие.
Помогаешь менеджеру подобрать материалы. Говоришь прямо и по-простому, можешь пошутить.
Знаешь нормы расхода как свои пять пальцев — ГЭСН, СНиП, всё это.
Знаешь цены Москвы 2026 года. Знаешь чем Кнауф отличается от Волмы и когда это важно.

ВАЖНО:
- Отвечай ТОЛЬКО валидным JSON. Никакого текста до или после.
- Если что-то непонятно — задай вопрос через clarifying_question (один вопрос за раз).
- В agent_comment можешь пошутить или дать совет от себя — коротко.
- ВСЕГДА указывай purchase_price и client_price (даже примерные).
- Если материал не в каталоге — придумай разумную цену по рынку.

Верни JSON строго в этом формате:
{
  "materials": [
    {
      "key": "ключ_из_каталога_или_новый_уникальный",
      "name": "Название материала",
      "unit": "меш. 30кг",
      "norm_per_unit": 0.6,
      "qty_total": 27.0,
      "variant": "стандарт",
      "purchase_price": 850,
      "client_price": 1050,
      "note": ""
    }
  ],
  "clarifying_question": null,
  "agent_comment": "Комментарий Палыча — можно с юмором"
}"""


def suggest_materials(
    work_name: str,
    work_qty: float,
    work_unit: str,
    existing_materials: list,
    user_message: str,
    api_key: str,
    memory: list = None,
) -> dict:
    """
    Claude подбирает материалы для работы.
    memory: список прошлых правок [{material, unit, purchase_price, client_price, date}]
    Возвращает {materials: [...], clarifying_question: str|None, agent_comment: str}
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Компактный каталог для промпта
    catalog_text = "\n".join(
        f"- {key}: {mat['name']} ({mat['unit']}) | "
        f"эконом: {mat['variants']['эконом']['brand']} | "
        f"стандарт: {mat['variants']['стандарт']['brand']} | "
        f"премиум: {mat['variants']['премиум']['brand']}"
        for key, mat in MATERIAL_CATALOG.items()
    )

    existing_text = ""
    if existing_materials:
        _ex_lines = []
        for _m in existing_materials:
            _brand = _m.get("brand") or _m.get("name", "?")
            _qty   = _m.get("qty_total", "?")
            _unit  = _m.get("unit", "")
            _var   = _m.get("variant", "")
            _ex_lines.append(f"  - {_brand} — {_qty} {_unit} [{_var}]")
        existing_text = (
            "УЖЕ ДОБАВЛЕНО (НЕ ДУБЛИРОВАТЬ эти позиции!\n"
            "Добавляй только то чего здесь нет, или явно напиши что надо изменить):\n"
            + "\n".join(_ex_lines) + "\n\n"
        )

    # Включаем память о прошлых правках
    memory_text = ""
    if memory:
        mem_lines = [
            f"  - {m.get('name', m.get('material','?'))} ({m.get('unit','')}) — наша закупка: {m.get('purchase_price',0)} ₽, клиент: {m.get('client_price',0)} ₽"
            for m in memory[-15:]
        ]
        memory_text = "НАШИ ЗАКУПОЧНЫЕ ЦЕНЫ (из прошлых смет):\n" + "\n".join(mem_lines) + "\n\n"

    prompt = (
        f"РАБОТА: {work_name}\n"
        f"ОБЪЁМ: {work_qty} {work_unit}\n\n"
        f"{memory_text}"
        f"{existing_text}"
        f"КАТАЛОГ МАТЕРИАЛОВ:\n{catalog_text}\n\n"
        f"МЕНЕДЖЕР ПИШЕТ: {user_message}"
    )

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=MATERIALS_AGENT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    # Убираем markdown-обёртки
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Если JSON внутри текста — вытаскиваем его
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        raw = json_match.group()

    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        # Fallback: агент объяснил текстом — показываем как комментарий
        result = {
            "materials": [],
            "clarifying_question": None,
            "agent_comment": raw[:300] if raw else "Попробуйте описать материалы подробнее.",
        }

    # Обогащаем ответ ценами из каталога
    for m in result.get("materials", []):
        key     = m.get("key", "")
        variant = m.get("variant", "стандарт")
        if key in MATERIAL_CATALOG and variant in MATERIAL_CATALOG[key]["variants"]:
            v = MATERIAL_CATALOG[key]["variants"][variant]
            m["purchase_price"] = v["purchase"]
            m["client_price"]   = v["client"]
            m["brand"]          = v["brand"]
        else:
            # Материал не в каталоге — помечаем для ручного заполнения
            m["purchase_price"] = m.get("purchase_price", 0)
            m["client_price"]   = m.get("client_price", 0)
            m["brand"]          = m.get("brand", m.get("name", ""))

    return result


def calc_material_totals(materials: list, work_qty: float) -> list:
    """Пересчитывает qty_total по norm_per_unit × work_qty."""
    result = []
    for m in materials:
        norm = m.get("norm_per_unit", 0)
        total = round(norm * work_qty, 2) if norm else m.get("qty_total", 0)
        result.append({**m, "qty_total": total})
    return result


def format_materials_for_excel(
    materials: list,
    work_qty: float,
    show_detail: bool = True,
) -> list[dict]:
    """
    Подготавливает материалы для вывода в Excel.
    Возвращает строки: name, brand, unit, qty, client_price, total_client
    Закупочная цена НЕ включается.
    """
    rows = []
    for m in calc_material_totals(materials, work_qty):
        client_p = m.get("client_price", 0)
        qty      = m.get("qty_total", 0)
        rows.append({
            "name":         m.get("name", ""),
            "brand":        m.get("brand", ""),
            "unit":         m.get("unit", ""),
            "qty":          qty,
            "client_price": client_p,
            "total_client": int(client_p * qty),
        })
    return rows
