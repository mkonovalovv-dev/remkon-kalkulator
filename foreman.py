# foreman.py — Прораб-агент: экспертная проверка состава КП
# Использует Claude Sonnet для профессионального разбора позиций
import json, re

FOREMAN_SYSTEM = """Ты — опытный прораб и сметчик с 35-летним стажем на строительных объектах в России.
Ты работал на промышленных, жилых и коммерческих объектах. Отлично знаешь:
- ГЭСН, ГЭСНм, ФЕР, ФЕРм — нормативные сборники
- Расход материалов по СНиП, СП, ГОСТ
- Реальные рыночные цены на работы в Москве (2024-2025)
- Что бывает «за кадром» в коммерческих ТЗ: что заказчик имеет в виду vs что написано
- Типичные ошибки молодых сметчиков и менеджеров по продажам

Твоя задача — проверить предварительный состав КП ПЕРЕД отправкой заказчику.
Ты должен найти:
1. Позиции с неясным объёмом/составом работ (нужно уточнить у заказчика)
2. Недостающие работы или материалы которые ОБЯЗАТЕЛЬНО идут вместе
3. Позиции где цена явно ниже рынка при данном объёме (риск убытка)
4. Позиции которые могут быть неправильно интерпретированы (смета vs реальность)

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
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Если JSON сломан — возвращаем как текст
        return {
            "verdict": "⚠️ Ответ прораба получен",
            "summary": raw[:500],
            "unclear_positions": [],
            "missing_items": [],
            "price_risks": [],
            "foreman_notes": [raw],
        }
