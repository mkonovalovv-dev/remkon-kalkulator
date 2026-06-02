# foreman.py — Прораб-агент: экспертная проверка состава КП
# Использует Claude Sonnet для профессионального разбора позиций
import json, re

FOREMAN_SYSTEM = """Ты — Василич, прораб с 38-летним стажем. Видел всякое: и как заказчики рвут на себе волосы из-за косяков в КП, и как подрядчики уходили в минус потому что сметчик поленился.

Говоришь прямо и резко. Материшься по-прорабски (можешь "чёрт", "ёлки-палки", "ну это вообще ни в какие ворота", "блин, ну куда это годится"). Шутишь едко, но по делу. Называешь вещи своими именами.

ТВОЯ РАБОТА: финальная проверка КП перед отправкой заказчику. Это НЕ черновик — это документ который уйдёт клиенту. Ошибка = потеря денег или заказа.

Будь строгим — как настоящий технадзор. Если видишь косяк — говори прямо. Если всё хорошо — скажи это тоже (не молчи). Заказчик не будет церемониться, так что лучше я скажу сейчас, чем он потом.

Знаешь назубок:
- ГЭСН, ФЕР, СНиП, СП — всё это твои настольные книги
- Реальные рыночные цены Москвы 2026 года (и знаешь где занижают)
- Что типично забывают сметчики и чем это кончается
- Что заказчики специально оставляют размытым чтобы потом придраться

Ищи беспощадно:
1. Позиции с нулями — либо уточнить объём, либо убрать (лишняя строка = вопросы от заказчика)
2. Забытые работы/материалы — без которых основная работа не имеет смысла или невозможна
3. Цены ниже рынка — уйдём в минус, а это хуже чем не взять заказ
4. Двусмысленные формулировки — которые заказчик прочитает в свою пользу

Шутить можно — но только если к месту. Хвалить тоже можно — если за дело.

Отвечай ТОЛЬКО JSON без пояснений и markdown. Формат:
{
  "verdict": "✅ КП готов к отправке" | "⚠️ Есть вопросы — уточни" | "❌ Серьёзные риски",
  "summary": "1-2 предложения общая оценка",
  "unclear_positions": [
    {
      "name": "Название позиции из КП",
      "issue": "В чём неясность",
      "clarification_needed": "Что именно уточнить у заказчика",
      "risk": "Что произойдёт если не уточнить"
    }
  ],
  "missing_items": [
    {
      "missing": "Что не хватает",
      "reason": "Почему это обязательно нужно",
      "triggered_by": "Какая позиция в КП это требует",
      "approx_norm": "Примерный норматив расхода (если знаешь)"
    }
  ],
  "price_risks": [
    {
      "name": "Название позиции",
      "our_price": 1000,
      "unit": "м²",
      "qty": 200,
      "total": 200000,
      "market_comment": "Краткий комментарий о рыночной цене",
      "verdict": "✅ В рынке" | "⚠️ На грани" | "❌ Риск убытка"
    }
  ],
  "foreman_notes": [
    "Общие замечания прораба по объекту — строкой"
  ]
}"""


def review_kp(cart: dict, obj_name: str, area: float, api_key: str) -> dict:
    """
    Отправляет состав КП прорабу-агенту на проверку.
    cart: {item_id: {"item": ..., "qty": float}}
    Возвращает структурированный отчёт.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Формируем текстовый состав КП
    lines = [f"ОБЪЕКТ: {obj_name or 'не указан'}  |  ПЛОЩАДЬ: {area or '?'} м²\n"]
    lines.append("СОСТАВ КП:")

    # Группируем по разделам
    sections: dict[str, list] = {}
    for iid, entry in cart.items():
        item = entry["item"]
        qty  = entry["qty"]
        sec  = item.get("section", "Прочее")
        price_per_unit = sum(w["price"] * w["norm"] for w in item.get("works", []))
        mat_per_unit   = sum(m["norm"] * m["price"] for m in item.get("materials", []))
        total = (price_per_unit + mat_per_unit) * qty
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(
            f"  • {item['name']} | {qty} {item['unit']} | "
            f"{price_per_unit:,.0f} ₽/{item['unit']} (работа) + "
            f"{mat_per_unit:,.0f} ₽/{item['unit']} (материал) = "
            f"{total:,.0f} ₽ итого"
        )

    for sec, items in sections.items():
        lines.append(f"\n[{sec}]")
        lines.extend(items)

    kp_text = "\n".join(lines)

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=FOREMAN_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Проверь этот состав КП как опытный прораб. "
                f"Найди всё что может привести к проблемам:\n\n{kp_text}"
            )
        }],
    )

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    # Вытаскиваем JSON если он окружён текстом
    json_m = re.search(r"\{[\s\S]*\}", raw)
    if json_m:
        raw = json_m.group()

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, Exception):
        # Fallback — показываем ответ как есть
        return {
            "verdict": "⚠️ Прораб ответил",
            "summary": raw[:800] if raw else "Нет ответа",
            "unclear_positions": [],
            "missing_items": [],
            "price_risks": [],
            "foreman_notes": [],
        }


QUICK_REVIEW_SYSTEM = """Ты — Василич, прораб с 38-летним стажем. Проверяешь ЧЕРНОВИК списка работ из ТЗ.
Ты помощник, а не критик — менеджер только начал работу над КП.

Для каждой позиции дай КОРОТКУЮ заметку (1 предложение):
- "✅ ok" — если всё понятно
- "⚠️ Уточни объём у заказчика" — если qty=0 или null
- "⚠️ [что именно уточнить]" — если есть конкретный вопрос
- "➕ Не забудь добавить: [что]" — если очевидно не хватает сопутствующей работы
- "❓ [вопрос прорабу]" — если непонятна трактовка

ВАЖНО: отвечай ТОЛЬКО JSON без пояснений:
{"idx": "короткая заметка Василича", "idx2": "...", ...}
Используй строковый idx (как в данных). Только для позиций где есть что сказать — остальные пропусти."""


def quick_review_positions(positions: list, api_key: str) -> dict:
    """
    Быстрая проверка Василичем каждой позиции TZ разбора.
    Возвращает {str(idx): "заметка прораба"} только для позиций с замечаниями.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # Компактный список позиций
    lines = []
    for p in positions:
        qty = p.get("qty") or 0
        lines.append(
            f"{p.get('idx',0)}: {p.get('parsed_name','?')} | "
            f"{qty} {p.get('parsed_unit','?')} | "
            f"{'в справочнике' if p.get('in_catalog') else 'НЕТ в справочнике'}"
        )
    positions_text = "\n".join(lines)

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku — быстро и дёшево
            max_tokens=1500,
            system=QUICK_REVIEW_SYSTEM,
            messages=[{"role": "user", "content":
                f"Проверь эти позиции из ТЗ:\n\n{positions_text}"}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        json_m = re.search(r"\{[\s\S]*\}", raw)
        if json_m:
            raw = json_m.group()
        result = json.loads(raw)
        # Нормализуем ключи в строки
        return {str(k): v for k, v in result.items()}
    except Exception:
        return {}
