# chains.py — Цепочки работ для умного калькулятора объёмов
# Каждая цепочка: вводные параметры → вычисленные объёмы → список позиций из справочника

# Формат цепочки:
#   inputs:   [{id, label, unit, default}]  — что вводит пользователь
#   computed: {id: (expr_str, unit, label)} — вычисляется из inputs через eval
#   chain:    [{keywords, qty_id, note, section_filter}]
#             keywords — список слов для поиска в name (ВСЕ lowercase)
#             qty_id   — ключ из inputs или computed (None = ввести вручную)
#             note     — подпись рядом с количеством
#             section_filter — раздел справочника (None = любой)

CHAINS = {
    "Возведение перегородок": {
        "emoji": "🧱",
        "label": "Перегородки: кладка, отделка, малярка",
        "inputs": [
            {"id": "perimeter", "label": "Периметр перегородок", "unit": "м.п.", "default": 0.0},
            {"id": "height",    "label": "Высота помещения",       "unit": "м",    "default": 3.0},
            {"id": "bh_mm",     "label": "Высота блока",           "unit": "мм",   "default": 200, "advanced": True},
        ],
        "computed": {
            "area":     ("round(perimeter * height, 2)",                      "м²",   "Площадь стен (1 стор.)"),
            "area2":    ("round(perimeter * height * 2, 2)",                  "м²",   "Площадь стен (2 стор.)"),
            "arm_rows": ("round(perimeter * max(1, height / (bh_mm/1000*3)), 1)", "м.п.", "Армирование (каждые 3 ряда)"),
        },
        "chain": [
            # Подготовка основания
            {"keywords": ["выравнивание", "основани"],          "qty_id": "perimeter", "note": "под перегородку",       "section": None},
            # Кладка (газобетон или кирпич — пользователь выберет)
            {"keywords": ["кладка", "газобетон"],               "qty_id": "area",      "note": "площадь кладки",        "section": "Возведение перегородок"},
            {"keywords": ["кладка", "кирпич"],                  "qty_id": "area",      "note": "площадь кладки",        "section": "Возведение перегородок"},
            # Армирование
            {"keywords": ["армирование", "кладк"],              "qty_id": "arm_rows",  "note": "каждые 3 ряда",         "section": None},
            # Примыкание к потолку
            {"keywords": ["примыкание", "потолк"],              "qty_id": "perimeter", "note": "периметр",              "section": None},
            # Штукатурка
            {"keywords": ["штукатурка", "гипс", "стен"],        "qty_id": "area2",     "note": "× 2 стороны",           "section": "Штукатурные работы"},
            {"keywords": ["штукатурка", "цпс", "стен"],         "qty_id": "area2",     "note": "× 2 стороны",           "section": "Штукатурные работы"},
            # Грунтовка + шпаклёвка + покраска (малярные)
            {"keywords": ["грунтовка"],                         "qty_id": "area2",     "note": "× 2 стороны",           "section": "Малярные работы"},
            {"keywords": ["шпаклёвка", "3"],                    "qty_id": "area2",     "note": "× 2 стороны",           "section": "Малярные работы"},
            {"keywords": ["покраска", "2"],                     "qty_id": "area2",     "note": "× 2 стороны",           "section": "Малярные работы"},
            # Плинтус
            {"keywords": ["плинтус"],                           "qty_id": "perimeter", "note": "× 2 стороны → вручную", "section": "Молдинги и плинтусы"},
        ],
    },

    "ГКЛ (гипсокартон)": {
        "emoji": "🗂️",
        "label": "ГКЛ-стены: отделка и малярка",
        "inputs": [
            {"id": "area_gkl",  "label": "Площадь ГКЛ-стен/перегородок", "unit": "м²",   "default": 0.0},
            {"id": "perimeter", "label": "Периметр",                      "unit": "м.п.", "default": 0.0},
        ],
        "computed": {},
        "chain": [
            {"keywords": ["грунтовка", "гкл"],                  "qty_id": "area_gkl",  "note": "",            "section": "Малярные работы"},
            {"keywords": ["подготовка", "гкл"],                 "qty_id": "area_gkl",  "note": "",            "section": "Малярные работы"},
            {"keywords": ["шпаклёвка", "3"],                    "qty_id": "area_gkl",  "note": "",            "section": "Малярные работы"},
            {"keywords": ["покраска", "2"],                     "qty_id": "area_gkl",  "note": "",            "section": "Малярные работы"},
            {"keywords": ["плинтус"],                           "qty_id": "perimeter", "note": "",            "section": "Молдинги и плинтусы"},
        ],
    },

    "Стяжка полов": {
        "emoji": "🪨",
        "label": "Стяжка → финишный пол",
        "inputs": [
            {"id": "area", "label": "Площадь пола", "unit": "м²", "default": 0.0},
        ],
        "computed": {},
        "chain": [
            {"keywords": ["грунтовка"],                         "qty_id": "area",   "note": "",  "section": "Стяжка полов"},
            {"keywords": ["стяжка", "цпс", "80"],               "qty_id": "area",   "note": "",  "section": "Стяжка полов"},
            {"keywords": ["наливной пол"],                      "qty_id": "area",   "note": "",  "section": "Стяжка полов"},
            {"keywords": ["ламинат"],                           "qty_id": "area",   "note": "",  "section": "Финишные полы"},
            {"keywords": ["кварц-винил", "клей"],               "qty_id": "area",   "note": "",  "section": "Финишные полы"},
            {"keywords": ["паркет", "наклеиванием"],            "qty_id": "area",   "note": "",  "section": "Финишные полы"},
        ],
    },

    "Плиточные работы": {
        "emoji": "🔲",
        "label": "Плитка: пол + стены (С/У, кухня)",
        "inputs": [
            {"id": "area_floor", "label": "Площадь пола",  "unit": "м²", "default": 0.0},
            {"id": "area_walls", "label": "Площадь стен",  "unit": "м²", "default": 0.0},
        ],
        "computed": {
            "total": ("round(area_floor + area_walls, 2)", "м²", "Общая площадь"),
        },
        "chain": [
            {"keywords": ["гидроизоляция", "2"],    "qty_id": "area_floor", "note": "пол",    "section": "Плиточные работы"},
            {"keywords": ["плитка", "пол", "601"],  "qty_id": "area_floor", "note": "пол",    "section": "Плиточные работы"},
            {"keywords": ["плитка", "стен"],        "qty_id": "area_walls", "note": "стены",  "section": "Плиточные работы"},
            {"keywords": ["затирка", "цемент"],     "qty_id": "total",      "note": "",       "section": "Плиточные работы"},
            {"keywords": ["затирка", "эпоксид"],    "qty_id": "total",      "note": "",       "section": "Плиточные работы"},
            {"keywords": ["плинтус"],               "qty_id": None,         "note": "ввести", "section": "Молдинги и плинтусы"},
        ],
    },

    "Малярные работы": {
        "emoji": "🎨",
        "label": "Малярка: стены + потолок",
        "inputs": [
            {"id": "area_walls", "label": "Площадь стен",    "unit": "м²", "default": 0.0},
            {"id": "area_ceil",  "label": "Площадь потолка", "unit": "м²", "default": 0.0},
        ],
        "computed": {
            "total": ("round(area_walls + area_ceil, 2)", "м²", "Итого поверхность"),
        },
        "chain": [
            {"keywords": ["грунтовка"],          "qty_id": "total",      "note": "",        "section": "Малярные работы"},
            {"keywords": ["шпаклёвка", "3"],     "qty_id": "area_walls", "note": "стены",   "section": "Малярные работы"},
            {"keywords": ["покраска", "2"],      "qty_id": "area_walls", "note": "стены",   "section": "Малярные работы"},
            {"keywords": ["потолок", "покраска"],"qty_id": "area_ceil",  "note": "потолок", "section": "Потолочные работы"},
        ],
    },

    "Штукатурные работы": {
        "emoji": "🪣",
        "label": "Штукатурка → малярка",
        "inputs": [
            {"id": "area", "label": "Площадь стен под штукатурку", "unit": "м²", "default": 0.0},
        ],
        "computed": {},
        "chain": [
            {"keywords": ["контактный слой", "грунт"],  "qty_id": "area", "note": "", "section": "Штукатурные работы"},
            {"keywords": ["штукатурка", "гипс", "стен"],"qty_id": "area", "note": "", "section": "Штукатурные работы"},
            {"keywords": ["грунтовка"],                  "qty_id": "area", "note": "", "section": "Малярные работы"},
            {"keywords": ["шпаклёвка", "3"],             "qty_id": "area", "note": "", "section": "Малярные работы"},
            {"keywords": ["покраска", "2"],              "qty_id": "area", "note": "", "section": "Малярные работы"},
        ],
    },

    "Потолочные работы": {
        "emoji": "⬜",
        "label": "Потолок: натяжной / ГКЛ / покраска",
        "inputs": [
            {"id": "area", "label": "Площадь потолка", "unit": "м²", "default": 0.0},
        ],
        "computed": {},
        "chain": [
            {"keywords": ["грунтовка"],              "qty_id": "area", "note": "",  "section": "Малярные работы"},
            {"keywords": ["натяжной потолок"],       "qty_id": "area", "note": "",  "section": "Потолочные работы"},
            {"keywords": ["потолок", "гкл", "лист"], "qty_id": "area", "note": "",  "section": "ГКЛ (гипсокартон)"},
            {"keywords": ["покраска", "2"],          "qty_id": "area", "note": "",  "section": "Малярные работы"},
        ],
    },

    "Электромонтаж (черновой)": {
        "emoji": "⚡",
        "label": "Электрика черновая → финишная",
        "inputs": [
            {"id": "area", "label": "Площадь помещения", "unit": "м²", "default": 0.0},
            {"id": "n_out", "label": "Кол-во розеток/выключателей", "unit": "шт.", "default": 0},
        ],
        "computed": {
            "cable_m": ("round(area * 0.8, 0)", "м.п.", "Примерная длина кабеля 2.5мм²"),
        },
        "chain": [
            {"keywords": ["кабель", "крепёж", "2,5"],     "qty_id": "cable_m", "note": "≈0.8м/м²",    "section": "Электромонтаж (черновой)"},
            {"keywords": ["подрозетник"],                  "qty_id": "n_out",   "note": "",             "section": "Электромонтаж (черновой)"},
            {"keywords": ["розетка"],                      "qty_id": "n_out",   "note": "",             "section": "Финишная электрика"},
            {"keywords": ["светильник", "точечный"],       "qty_id": None,      "note": "ввести",       "section": "Финишная электрика"},
        ],
    },

    "Сантехника (черновая)": {
        "emoji": "🚿",
        "label": "Сантехника черновая → финишная",
        "inputs": [
            {"id": "n_wc",     "label": "Унитазов",          "unit": "шт.", "default": 0},
            {"id": "n_sink",   "label": "Раковин",           "unit": "шт.", "default": 0},
            {"id": "n_shower", "label": "Душевых кабин/ванн","unit": "шт.", "default": 0},
            {"id": "pipe_m",   "label": "Длина трубопровода","unit": "м.п.", "default": 0.0},
        ],
        "computed": {
            "n_sinks_total": ("n_wc + n_sink + n_shower", "шт.", "Итого точек"),
        },
        "chain": [
            {"keywords": ["канализация", "d50"],    "qty_id": "pipe_m",        "note": "",  "section": "Сантехника (черновая)"},
            {"keywords": ["водопровод", "d16"],      "qty_id": "pipe_m",        "note": "",  "section": "Сантехника (черновая)"},
            {"keywords": ["инсталляция"],            "qty_id": "n_wc",          "note": "",  "section": "Сантехника (черновая)"},
            {"keywords": ["унитаз", "инсталляц"],    "qty_id": "n_wc",          "note": "",  "section": "Финишная сантехника"},
            {"keywords": ["раковина"],               "qty_id": "n_sink",        "note": "",  "section": "Финишная сантехника"},
            {"keywords": ["смеситель", "раковин"],   "qty_id": "n_sink",        "note": "",  "section": "Финишная сантехника"},
            {"keywords": ["поддон", "душевой"],      "qty_id": "n_shower",      "note": "",  "section": "Плиточные работы"},
        ],
    },
}


def find_chain_items(chain_def: dict, all_items: list) -> list:
    """
    По цепочке chain_def ищет подходящие позиции из all_items.
    Возвращает список dict:
      {item, qty_id, note, matched}
    """
    results = []
    chain = chain_def.get("chain", [])
    for step in chain:
        keywords = [k.lower() for k in step["keywords"]]
        sec_filter = step.get("section")
        candidates = []
        for item in all_items:
            if sec_filter and item["section"] != sec_filter:
                continue
            name_lower = item["name"].lower()
            if all(kw in name_lower for kw in keywords):
                candidates.append(item)
        if candidates:
            results.append({
                "item": candidates[0],   # берём первый подходящий
                "qty_id": step["qty_id"],
                "note": step["note"],
            })
    return results
