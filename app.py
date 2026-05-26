# app.py — Калькулятор КП Ремкон
# Запуск: streamlit run app.py

import streamlit as st
from datetime import date
from data_loader import load_data, get_sections, get_subsections, get_items
from exporter import generate_excel

# ─────────────────────────────────────────────
# НАСТРОЙКА СТРАНИЦЫ
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Калькулятор КП — Ремкон",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# ПАРОЛЬ
# ─────────────────────────────────────────────
def check_password() -> bool:
    correct_pwd = st.secrets.get("APP_PASSWORD", "Remkon2026")

    if st.session_state.get("authenticated"):
        return True

    with st.container():
        st.title("🏗️ Калькулятор КП — Ремкон")
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            pwd = st.text_input("Введите пароль для входа", type="password", key="pwd_input")
            if st.button("Войти", type="primary", use_container_width=True):
                if pwd == correct_pwd:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Неверный пароль")
    return False


if not check_password():
    st.stop()

# ─────────────────────────────────────────────
# ЗАГОЛОВОК
# ─────────────────────────────────────────────
st.title("🏗️ Калькулятор КП — Ремкон")
st.markdown("---")

# ─────────────────────────────────────────────
# ЗАГРУЗКА ДАННЫХ
# ─────────────────────────────────────────────
all_items = load_data()

# ─────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ SESSION STATE
# ─────────────────────────────────────────────
from default_data import SECTION_ORDER as DEFAULT_SECTION_ORDER

if "section_order" not in st.session_state:
    st.session_state["section_order"] = list(DEFAULT_SECTION_ORDER)
if "custom_items" not in st.session_state:
    st.session_state["custom_items"] = []
if "adding_to_section" not in st.session_state:
    st.session_state["adding_to_section"] = None

# Объединяем базовые + пользовательские позиции
all_items_combined = all_items + st.session_state["custom_items"]

# ─────────────────────────────────────────────
# ШАГ 0: ИНФОРМАЦИЯ ОБ ОБЪЕКТЕ
# ─────────────────────────────────────────────
with st.expander("📋 Информация об объекте", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        client = st.text_input("Заказчик", placeholder="ООО «Пример»")
        address = st.text_input("Адрес объекта", placeholder="г. Москва, ул. …")
    with col2:
        obj_name = st.text_input("Название объекта", placeholder="Офис / склад / ресторан")
        area = st.number_input("Площадь объекта, м²", min_value=0.0, step=1.0, format="%.1f")
        height = st.number_input("Высота помещения, м", min_value=2.0, max_value=10.0,
                                 step=0.1, value=3.0, format="%.1f")
    with col3:
        proj_date = st.date_input("Дата КП", value=date.today())
        manager = st.text_input("Менеджер", placeholder="Имя продажника")

st.markdown("---")

# ─────────────────────────────────────────────
# КОНСТРУКТОР РАЗДЕЛОВ
# ─────────────────────────────────────────────
with st.expander("🔧 Конструктор разделов и позиций", expanded=False):
    st.caption("Меняйте порядок разделов ↕ · Создавайте свои разделы · Добавляйте произвольные позиции")

    section_order = st.session_state["section_order"]

    # ── Список разделов с кнопками управления ──
    for idx, section in enumerate(section_order):
        col_up, col_down, col_name, col_add, col_del = st.columns([0.5, 0.5, 5, 2.5, 0.7])

        with col_up:
            if idx > 0:
                if st.button("▲", key=f"sec_up_{idx}", help="Переместить выше"):
                    so = st.session_state["section_order"]
                    so[idx - 1], so[idx] = so[idx], so[idx - 1]
                    st.rerun()

        with col_down:
            if idx < len(section_order) - 1:
                if st.button("▼", key=f"sec_down_{idx}", help="Переместить ниже"):
                    so = st.session_state["section_order"]
                    so[idx], so[idx + 1] = so[idx + 1], so[idx]
                    st.rerun()

        with col_name:
            # Отмечаем пользовательские разделы
            is_custom_sec = section not in DEFAULT_SECTION_ORDER
            label = f"**{section}**" + (" 🟡" if is_custom_sec else "")
            st.markdown(label)

        with col_add:
            if st.button(f"➕ Добавить позицию", key=f"btn_add_{idx}", use_container_width=True):
                if st.session_state["adding_to_section"] == section:
                    st.session_state["adding_to_section"] = None
                else:
                    st.session_state["adding_to_section"] = section
                st.rerun()

        with col_del:
            # Удалять можно только пользовательские пустые разделы
            if is_custom_sec:
                has_items = any(i["section"] == section for i in st.session_state["custom_items"])
                if not has_items:
                    if st.button("🗑", key=f"sec_del_{idx}", help="Удалить раздел"):
                        st.session_state["section_order"].remove(section)
                        st.rerun()

        # ── Форма добавления позиции ──
        if st.session_state["adding_to_section"] == section:
            with st.container():
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📌 **Новая позиция → {section}**")
                fc1, fc2, fc3, fc4 = st.columns([3, 1.2, 1.2, 1.5])
                with fc1:
                    new_name = st.text_input(
                        "Название работы", placeholder="Например: Установка стеклянной перегородки",
                        key=f"inp_name_{section}"
                    )
                with fc2:
                    new_unit = st.text_input("Единица", value="кв.м.", key=f"inp_unit_{section}")
                with fc3:
                    new_price = st.number_input(
                        "Цена за ед., ₽", min_value=0, step=100, key=f"inp_price_{section}"
                    )
                with fc4:
                    new_subsection = st.text_input(
                        "Подраздел", placeholder="(опционально)", key=f"inp_sub_{section}"
                    )

                btn_save, btn_cancel = st.columns([1, 1])
                with btn_save:
                    if st.button("✅ Сохранить позицию", key=f"save_{section}", type="primary", use_container_width=True):
                        if new_name.strip():
                            import uuid
                            new_item = {
                                "id": f"custom_{uuid.uuid4().hex[:8]}",
                                "section": section,
                                "subsection": new_subsection.strip() or "Пользовательские позиции",
                                "name": new_name.strip(),
                                "unit": new_unit.strip() or "шт.",
                                "works": [{
                                    "name": new_name.strip(),
                                    "unit": new_unit.strip() or "шт.",
                                    "price": int(new_price),
                                    "norm": 1.0
                                }],
                                "materials": [],
                            }
                            st.session_state["custom_items"].append(new_item)
                            st.session_state["adding_to_section"] = None
                            st.success(f"✅ Позиция «{new_name}» добавлена в «{section}»")
                            st.rerun()
                        else:
                            st.warning("Введите название работы")
                with btn_cancel:
                    if st.button("✖ Отмена", key=f"cancel_{section}", use_container_width=True):
                        st.session_state["adding_to_section"] = None
                        st.rerun()
                st.markdown("---")

    # ── Показать текущие пользовательские позиции ──
    if st.session_state["custom_items"]:
        with st.expander(f"📋 Мои позиции ({len(st.session_state['custom_items'])} шт.)", expanded=False):
            for ci_idx, ci in enumerate(st.session_state["custom_items"]):
                price_show = ci["works"][0]["price"] if ci["works"] else 0
                cc1, cc2 = st.columns([5, 1])
                with cc1:
                    st.write(f"• [{ci['section']} / {ci.get('subsection','')}] **{ci['name']}** — {price_show:,} ₽ / {ci['unit']}")
                with cc2:
                    if st.button("🗑", key=f"del_ci_{ci_idx}", help="Удалить позицию"):
                        st.session_state["custom_items"].pop(ci_idx)
                        st.rerun()

    st.markdown("---")
    # ── Создать новый раздел ──
    st.markdown("**➕ Создать новый раздел:**")
    ns_col1, ns_col2 = st.columns([4, 1.5])
    with ns_col1:
        new_section_name = st.text_input(
            "Название нового раздела",
            placeholder="Например: Специальные работы / Благоустройство",
            key="new_section_name",
            label_visibility="collapsed",
        )
    with ns_col2:
        if st.button("Создать раздел ➕", type="primary", use_container_width=True):
            name = new_section_name.strip()
            if name and name not in st.session_state["section_order"]:
                st.session_state["section_order"].append(name)
                st.success(f"Раздел «{name}» создан!")
                st.rerun()
            elif name in st.session_state["section_order"]:
                st.warning("Такой раздел уже существует")
            else:
                st.warning("Введите название раздела")

    # ── Сброс к дефолтному порядку ──
    if st.button("🔄 Сбросить порядок разделов к стандартному", use_container_width=False):
        st.session_state["section_order"] = list(DEFAULT_SECTION_ORDER)
        st.rerun()

st.markdown("---")

# ─────────────────────────────────────────────
# ШАГ 1: ВЫБОР ВИДОВ РАБОТ
# ─────────────────────────────────────────────
st.subheader("Шаг 1 — Выберите виды работ")
st.caption("Ставьте ✓ на разделе → открываются подразделы → ставьте ✓ на нужных позициях")

# Используем порядок из session_state, показываем только разделы с позициями
sections_with_items = [
    s for s in st.session_state["section_order"]
    if any(i["section"] == s for i in all_items_combined)
]

selected_ids = []  # id выбранных позиций

for section in sections_with_items:
    sec_key = f"sec_{section}"
    sec_checked = st.checkbox(f"**{section}**", key=sec_key)

    if sec_checked:
        # Подразделы из объединённого списка
        subs = []
        for i in all_items_combined:
            if i["section"] == section:
                sub = i.get("subsection") or "Общее"
                if sub not in subs:
                    subs.append(sub)

        for subsection in subs:
            items_in_sub = [
                i for i in all_items_combined
                if i["section"] == section and (i.get("subsection") or "Общее") == subsection
            ]
            with st.expander(f"↳ {subsection}", expanded=True):
                for item in items_in_sub:
                    iid = item["id"]
                    approx_price = sum(
                        w["price"] * w["norm"]
                        for w in item.get("works", [])
                    )
                    is_custom = iid.startswith("custom_")
                    marker = " 🟡" if is_custom else ""
                    label = (
                        f"{item['name']}{marker}"
                        f"  —  **{approx_price:,.0f} ₽ / {item['unit']}**"
                    )
                    checked = st.checkbox(label, key=f"item_{iid}")
                    if checked:
                        selected_ids.append(iid)

# Словарь id → item для быстрого доступа
item_map = {i["id"]: i for i in all_items_combined}
selected_items = [item_map[iid] for iid in selected_ids]

st.markdown("---")

# ─────────────────────────────────────────────
# ШАГ 2: ОБЪЁМЫ РАБОТ
# ─────────────────────────────────────────────
quantities: dict = {}

if selected_items:
    st.subheader("Шаг 2 — Введите объёмы работ")
    st.caption("Укажите количество для каждой выбранной позиции")

    current_section = None
    current_subsection = None
    for item in selected_items:
        if item["section"] != current_section:
            current_section = item["section"]
            st.markdown(f"**{current_section}**")
        subsec = item.get("subsection") or "Общее"
        if subsec != current_subsection:
            current_subsection = subsec
            st.markdown(f"*{current_subsection}*")

        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"• {item['name']}")
        with col2:
            qty = st.number_input(
                label=item["unit"],
                min_value=0.0,
                step=0.5,
                format="%.2f",
                key=f"qty_{item['id']}",
                label_visibility="visible",
            )
        quantities[item["id"]] = qty

    st.markdown("---")

# ─────────────────────────────────────────────
# ШАГ 3: ДОПОЛНИТЕЛЬНЫЕ РАСХОДЫ И ФИНАНСЫ
# ─────────────────────────────────────────────
if selected_items:
    with st.expander("💼 Дополнительные расходы", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            extra_delivery = st.number_input(
                "Доставка материалов, ₽", min_value=0, step=1000, value=0
            )
            extra_trash = st.number_input(
                "Вывоз строительного мусора, ₽", min_value=0, step=1000, value=0
            )
        with col2:
            extra_unforeseen_pct = st.number_input(
                "Непредвиденные расходы, %", min_value=0, max_value=20, step=1, value=3
            )
            extra_cover = st.number_input(
                "Укрывные работы, ₽", min_value=0, step=500, value=0
            )
        with col3:
            extra_temp_elec = st.number_input(
                "Временное электроснабжение, ₽", min_value=0, step=500, value=0
            )
            extra_temp_water = st.number_input(
                "Временное водоснабжение, ₽", min_value=0, step=500, value=0
            )

    with st.expander("📊 Финансовые параметры КП", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            overhead_pct = st.number_input(
                "Накладные расходы, %",
                min_value=0, max_value=50, step=1, value=10,
                help="Процент от суммы работ и материалов"
            )
        with col2:
            profit_pct = st.number_input(
                "Прибыль, %",
                min_value=0, max_value=50, step=1, value=5,
                help="Процент от суммы работ и материалов"
            )
        with col3:
            vat_on = st.checkbox("НДС 22%", value=False,
                                 help="Включить НДС в итоговую сумму КП")

    fin_settings = {
        "overhead_pct": int(overhead_pct),
        "profit_pct": int(profit_pct),
        "vat": vat_on,
    }

    st.markdown("---")

# ─────────────────────────────────────────────
# ШАГ 4: ИТОГ И СКАЧИВАНИЕ
# ─────────────────────────────────────────────
if selected_items and any(quantities.get(i["id"], 0) > 0 for i in selected_items):
    st.subheader("Шаг 3 — Итог")

    total_work = 0.0
    total_mat = 0.0

    rows_preview = []
    for item in selected_items:
        qty = quantities.get(item["id"], 0)

        work_sum = sum(
            qty * w.get("norm", 1) * w.get("price", 0)
            for w in item.get("works", [])
        )
        mat_sum = sum(
            qty * m.get("norm", 0) * m.get("price", 0)
            for m in item.get("materials", [])
        )

        total_work += work_sum
        total_mat += mat_sum
        rows_preview.append({
            "Раздел": item["section"],
            "Позиция": item["name"],
            "Ед.": item["unit"],
            "Кол-во": qty,
            "Работы, ₽": int(work_sum),
            "Материалы, ₽": int(mat_sum),
            "Итого, ₽": int(work_sum + mat_sum),
        })

    try:
        base_total = total_work + total_mat
        unforeseen = base_total * extra_unforeseen_pct / 100
        extra_total = (
            extra_delivery + extra_trash + extra_cover
            + extra_temp_elec + extra_temp_water + unforeseen
        )
    except Exception:
        unforeseen = 0.0
        extra_total = 0.0

    subtotal = total_work + total_mat + extra_total
    try:
        overhead_sum = subtotal * fin_settings["overhead_pct"] / 100
        profit_sum = subtotal * fin_settings["profit_pct"] / 100
    except Exception:
        overhead_sum = 0.0
        profit_sum = 0.0
    total_before_vat = subtotal + overhead_sum + profit_sum
    vat_sum = total_before_vat * 0.20 if (fin_settings.get("vat") if "fin_settings" in dir() else False) else 0.0
    grand_total = total_before_vat + vat_sum

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Работы", f"{int(total_work):,} ₽".replace(",", " "))
    col2.metric("Материалы", f"{int(total_mat):,} ₽".replace(",", " "))
    col3.metric("Доп. расходы", f"{int(extra_total):,} ₽".replace(",", " "))
    col4.metric("ИТОГО", f"{int(grand_total):,} ₽".replace(",", " "))

    import pandas as pd
    df_preview = pd.DataFrame(rows_preview)
    st.dataframe(df_preview, use_container_width=True, hide_index=True)

    st.markdown("---")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📥 Сформировать Excel", type="primary", use_container_width=True):
            try:
                extra_costs = {
                    "Доставка материалов": extra_delivery,
                    "Вывоз строительного мусора": extra_trash,
                    "Укрывные работы": extra_cover,
                    "Временное электроснабжение": extra_temp_elec,
                    "Временное водоснабжение": extra_temp_water,
                    f"Непредвиденные расходы ({extra_unforeseen_pct}%)": int(unforeseen),
                }
                excel_bytes = generate_excel(
                    client=client,
                    address=address,
                    obj_name=obj_name,
                    area=area,
                    proj_date=proj_date,
                    manager=manager,
                    selected_items=selected_items,
                    quantities=quantities,
                    extra_costs=extra_costs,
                    fin_settings=fin_settings,
                )
                safe_client = (
                    client.replace(" ", "_")
                          .replace('"', "")
                          .replace("«", "")
                          .replace("»", "")
                ) or "КП"
                filename = f"КП_{safe_client}_{proj_date}.xlsx"
                st.session_state["excel_ready"] = True
                st.session_state["excel_bytes"] = excel_bytes
                st.session_state["excel_filename"] = filename
            except Exception as e:
                st.error(f"Ошибка генерации Excel: {e}")

    with col2:
        if st.session_state.get("excel_ready"):
            st.download_button(
                label="⬇️ Скачать КП",
                data=st.session_state["excel_bytes"],
                file_name=st.session_state["excel_filename"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary",
                use_container_width=True,
            )

elif not selected_items:
    st.info("👆 Выберите виды работ выше, чтобы сформировать КП")
else:
    st.info("👆 Введите объёмы работ для расчёта")

# ─────────────────────────────────────────────
# ПОДВАЛ
# ─────────────────────────────────────────────
st.markdown("---")
st.caption("ООО «Ремкон» · Калькулятор КП v1.2 · remkon.ru")
