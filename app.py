# app.py — Калькулятор КП Ремкон v1.3
# Запуск: streamlit run app.py

import streamlit as st
from datetime import date
import json, uuid, os, re
from data_loader import load_data
from exporter import generate_excel
from chains import CHAINS, find_chain_items
from default_data import SECTION_ORDER as DEFAULT_SECTION_ORDER

st.set_page_config(
    page_title="Калькулятор КП — Ремкон",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── ПАРОЛЬ ──────────────────────────────────────────────────────────────────
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    correct = st.secrets.get("APP_PASSWORD", "Remkon2026")
    st.title("🏗️ Калькулятор КП — Ремкон")
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        pwd = st.text_input("Пароль", type="password", key="pwd_input")
        if st.button("Войти", type="primary", use_container_width=True):
            if pwd == correct:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Неверный пароль")
    return False

if not check_password():
    st.stop()

# ─── ИНИЦИАЛИЗАЦИЯ STATE ──────────────────────────────────────────────────────
all_items = load_data()

if "section_order"    not in st.session_state:
    st.session_state["section_order"]    = list(DEFAULT_SECTION_ORDER)
if "custom_items"     not in st.session_state:
    st.session_state["custom_items"]     = []
if "adding_to_sec"    not in st.session_state:
    st.session_state["adding_to_sec"]    = None
if "chain_qtys"       not in st.session_state:
    st.session_state["chain_qtys"]       = {}   # {item_id: qty}
if "chain_checked"    not in st.session_state:
    st.session_state["chain_checked"]    = set() # item_ids, добавленных через мастер
if "kp_history"       not in st.session_state:
    # Загружаем из файла если есть
    hist_path = os.path.join(os.path.dirname(__file__), "kp_history.json")
    if os.path.exists(hist_path):
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                st.session_state["kp_history"] = json.load(f)
        except Exception:
            st.session_state["kp_history"] = []
    else:
        st.session_state["kp_history"] = []
if "loaded_kp"        not in st.session_state:
    st.session_state["loaded_kp"]        = None  # загруженный КП из истории

all_items_combined = all_items + st.session_state["custom_items"]

# ─── ВКЛАДКИ ─────────────────────────────────────────────────────────────────
st.title("🏗️ Калькулятор КП — Ремкон")
tab_kp, tab_tz, tab_hist = st.tabs(["📝 Составить КП", "🤖 Загрузить ТЗ (AI)", "📋 История КП"])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — СОСТАВИТЬ КП
# ════════════════════════════════════════════════════════════════════════════════
with tab_kp:

    # ── Информация об объекте ────────────────────────────────────────────────
    with st.expander("📋 Информация об объекте", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            client   = st.text_input("Заказчик",       placeholder="ООО «Пример»",       key="kp_client")
            address  = st.text_input("Адрес объекта",  placeholder="г. Москва, ул. …",   key="kp_address")
        with c2:
            obj_name = st.text_input("Название объекта", placeholder="Офис / склад",      key="kp_obj")
            area_obj = st.number_input("Площадь, м²",  min_value=0.0, step=1.0,           key="kp_area", format="%.1f")
            height   = st.number_input("Высота, м",    min_value=2.0, max_value=10.0,
                                       step=0.1, value=3.0, format="%.1f",                key="kp_height")
        with c3:
            proj_date = st.date_input("Дата КП", value=date.today(), key="kp_date")
            manager   = st.text_input("Менеджер", placeholder="Имя",                     key="kp_mgr")

    st.markdown("---")

    # ── Конструктор разделов (DnD) ───────────────────────────────────────────
    with st.expander("🔧 Конструктор разделов и позиций", expanded=False):
        st.caption("Перетащите разделы мышью · Создайте новый раздел · Добавьте свою позицию")

        # Drag & Drop через streamlit-sortables
        try:
            from streamlit_sortables import sort_items
            new_order = sort_items(
                st.session_state["section_order"],
                direction="vertical",
                key="sortable_sections",
            )
            if new_order != st.session_state["section_order"]:
                st.session_state["section_order"] = new_order
                st.rerun()
        except ImportError:
            # Fallback: кнопки ▲▼
            section_order = st.session_state["section_order"]
            for idx, sec in enumerate(section_order):
                cu, cd, cn, ca = st.columns([0.5, 0.5, 5, 2.5])
                with cu:
                    if idx > 0 and st.button("▲", key=f"up_{idx}"):
                        section_order[idx-1], section_order[idx] = section_order[idx], section_order[idx-1]
                        st.rerun()
                with cd:
                    if idx < len(section_order)-1 and st.button("▼", key=f"dn_{idx}"):
                        section_order[idx], section_order[idx+1] = section_order[idx+1], section_order[idx]
                        st.rerun()
                with cn:
                    st.write(sec)
                with ca:
                    if st.button("➕ Позицию", key=f"addp_{idx}", use_container_width=True):
                        st.session_state["adding_to_sec"] = sec if st.session_state["adding_to_sec"] != sec else None
                        st.rerun()

        st.markdown("---")

        # Кнопки добавления позиции (под каждым разделом, через selectbox)
        add_sec = st.selectbox(
            "Добавить позицию в раздел:",
            ["— выбрать —"] + st.session_state["section_order"],
            key="add_pos_sec_select",
        )
        if add_sec != "— выбрать —":
            fc1, fc2, fc3, fc4 = st.columns([3, 1.2, 1.2, 1.5])
            with fc1: new_name = st.text_input("Название работы", key="new_pos_name")
            with fc2: new_unit = st.text_input("Единица", value="кв.м.", key="new_pos_unit")
            with fc3: new_price = st.number_input("Цена ₽/ед.", min_value=0, step=100, key="new_pos_price")
            with fc4: new_sub = st.text_input("Подраздел", placeholder="опционально", key="new_pos_sub")
            if st.button("✅ Добавить позицию", type="primary"):
                if new_name.strip():
                    ci = {
                        "id": f"custom_{uuid.uuid4().hex[:8]}",
                        "section": add_sec,
                        "subsection": new_sub.strip() or "Пользовательские позиции",
                        "name": new_name.strip(),
                        "unit": new_unit.strip() or "шт.",
                        "works": [{"name": new_name.strip(), "unit": new_unit.strip() or "шт.",
                                   "price": int(new_price), "norm": 1.0}],
                        "materials": [],
                    }
                    st.session_state["custom_items"].append(ci)
                    all_items_combined = all_items + st.session_state["custom_items"]
                    st.success(f"Позиция «{new_name}» добавлена!")
                    st.rerun()
                else:
                    st.warning("Введите название")

        # Список пользовательских позиций
        if st.session_state["custom_items"]:
            st.markdown("---")
            st.markdown(f"**Мои позиции ({len(st.session_state['custom_items'])} шт.):**")
            for ci_idx, ci in enumerate(st.session_state["custom_items"]):
                price_show = ci["works"][0]["price"] if ci["works"] else 0
                cc1, cc2 = st.columns([8, 1])
                with cc1:
                    st.caption(f"[{ci['section']}] {ci['name']} — {price_show:,} ₽/{ci['unit']}")
                with cc2:
                    if st.button("🗑", key=f"del_ci_{ci_idx}"):
                        st.session_state["custom_items"].pop(ci_idx)
                        st.rerun()

        st.markdown("---")
        # Создать новый раздел
        st.markdown("**Создать новый раздел:**")
        ns1, ns2 = st.columns([4, 1.5])
        with ns1:
            new_sec_name = st.text_input("Название раздела", placeholder="Например: Благоустройство",
                                         key="new_sec_name", label_visibility="collapsed")
        with ns2:
            if st.button("Создать ➕", type="primary", use_container_width=True):
                name = new_sec_name.strip()
                if name and name not in st.session_state["section_order"]:
                    st.session_state["section_order"].append(name)
                    st.rerun()
                elif name:
                    st.warning("Уже существует")

        if st.button("🔄 Сбросить порядок к стандартному"):
            st.session_state["section_order"] = list(DEFAULT_SECTION_ORDER)
            st.rerun()

    st.markdown("---")

    # ── Шаг 1: Выбор работ + Умный помощник ─────────────────────────────────
    st.subheader("Шаг 1 — Выберите виды работ")
    st.caption("✓ раздел → подразделы → ✓ позиции  |  🧮 — умный расчёт объёмов и цепочек работ")

    sections_with_items = [
        s for s in st.session_state["section_order"]
        if any(i["section"] == s for i in all_items_combined)
    ]

    selected_ids = list(st.session_state.get("chain_checked", set()))

    for section in sections_with_items:
        col_sec, col_calc = st.columns([7, 1.5])
        with col_sec:
            sec_checked = st.checkbox(f"**{section}**", key=f"sec_{section}")
        with col_calc:
            if section in CHAINS:
                btn_label = "🧮 Мастер"
                if st.button(btn_label, key=f"chain_btn_{section}", use_container_width=True):
                    toggle_key = f"chain_open_{section}"
                    st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                    st.rerun()

        # ── Умный мастер расчёта ──────────────────────────────────────────
        if section in CHAINS and st.session_state.get(f"chain_open_{section}"):
            chain_def = CHAINS[section]
            with st.container():
                st.markdown(f"#### {chain_def['emoji']} Мастер: {chain_def['label']}")

                # Вводные параметры
                inp_vals = {}
                adv_visible = st.checkbox("Показать расширенные параметры", key=f"chain_adv_{section}")
                inp_cols = st.columns(min(len(chain_def["inputs"]), 4))
                for i, inp in enumerate(chain_def["inputs"]):
                    if inp.get("advanced") and not adv_visible:
                        inp_vals[inp["id"]] = inp["default"]
                        continue
                    with inp_cols[i % len(inp_cols)]:
                        val = st.number_input(
                            f"{inp['label']}, {inp['unit']}",
                            min_value=0.0, value=float(inp["default"]),
                            step=0.5, format="%.2f",
                            key=f"chain_inp_{section}_{inp['id']}",
                        )
                        inp_vals[inp["id"]] = val

                # Вычисленные значения
                computed_vals = dict(inp_vals)
                if chain_def.get("computed"):
                    st.markdown("**📐 Рассчитанные объёмы:**")
                    cv_cols = st.columns(min(len(chain_def["computed"]), 4))
                    for ci2, (cid, (expr, unit, clabel)) in enumerate(chain_def["computed"].items()):
                        try:
                            val = eval(expr, {"__builtins__": {}}, {**computed_vals, "max": max, "min": min, "round": round})
                        except Exception:
                            val = 0.0
                        computed_vals[cid] = val
                        with cv_cols[ci2 % len(cv_cols)]:
                            st.metric(f"{clabel}", f"{val} {unit}")

                # Найденные позиции справочника
                chain_matches = find_chain_items(chain_def, all_items_combined)
                if chain_matches:
                    st.markdown("**📋 Цепочка работ — выберите нужные:**")
                    for match in chain_matches:
                        item = match["item"]
                        qty_id = match["qty_id"]
                        note = match["note"]
                        qty_val = computed_vals.get(qty_id, 0.0) if qty_id else 0.0
                        iid = item["id"]

                        cm1, cm2, cm3 = st.columns([0.5, 5, 2])
                        with cm1:
                            checked_now = st.checkbox(
                                "", key=f"chain_chk_{section}_{iid}",
                                value=(iid in st.session_state["chain_checked"])
                            )
                        with cm2:
                            price_show = sum(w["price"] * w["norm"] for w in item.get("works", []))
                            st.write(f"**{item['name']}** — {price_show:,.0f} ₽/{item['unit']}")
                            st.caption(f"{item['section']} / {item.get('subsection','')}")
                        with cm3:
                            qty_edit = st.number_input(
                                f"{item['unit']} {('('+note+')') if note else ''}",
                                min_value=0.0, value=float(qty_val),
                                step=0.5, format="%.2f",
                                key=f"chain_qty_{section}_{iid}",
                            )
                            st.session_state["chain_qtys"][iid] = qty_edit

                        if checked_now:
                            st.session_state["chain_checked"].add(iid)
                        else:
                            st.session_state["chain_checked"].discard(iid)

                    if st.button(f"✅ Принять выбранные позиции мастера → в КП",
                                 key=f"chain_accept_{section}", type="primary"):
                        st.session_state[f"chain_open_{section}"] = False
                        st.success("Позиции добавлены! Прокрутите вниз к Шагу 2.")
                        st.rerun()
                else:
                    st.info("Совпадений в справочнике не найдено — выберите позиции вручную ниже.")

                st.markdown("---")

        # ── Обычный чекбокс-список ────────────────────────────────────────
        if sec_checked:
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
                        approx_price = sum(w["price"] * w["norm"] for w in item.get("works", []))
                        is_custom = iid.startswith("custom_")
                        is_chain  = iid in st.session_state["chain_checked"]
                        marker = " 🟡" if is_custom else (" ⚡" if is_chain else "")
                        label = (f"{item['name']}{marker}"
                                 f"  —  **{approx_price:,.0f} ₽ / {item['unit']}**")
                        checked = st.checkbox(label, key=f"item_{iid}",
                                              value=is_chain)
                        if checked and iid not in selected_ids:
                            selected_ids.append(iid)
                        elif not checked and iid in selected_ids:
                            selected_ids.remove(iid)

    item_map = {i["id"]: i for i in all_items_combined}
    selected_items = [item_map[iid] for iid in selected_ids if iid in item_map]

    st.markdown("---")

    # ── Шаг 2: Объёмы ────────────────────────────────────────────────────────
    quantities: dict = {}
    if selected_items:
        st.subheader("Шаг 2 — Объёмы работ")
        cur_sec = cur_sub = None
        for item in selected_items:
            if item["section"] != cur_sec:
                cur_sec = item["section"]
                st.markdown(f"**{cur_sec}**")
            sub = item.get("subsection") or "Общее"
            if sub != cur_sub:
                cur_sub = sub
                st.markdown(f"*{sub}*")
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(f"• {item['name']}")
            with c2:
                # Подставляем значение из мастера если есть
                default_qty = float(st.session_state["chain_qtys"].get(item["id"], 0.0))
                qty = st.number_input(
                    item["unit"], min_value=0.0, step=0.5, format="%.2f",
                    value=default_qty,
                    key=f"qty_{item['id']}", label_visibility="visible",
                )
            quantities[item["id"]] = qty
        st.markdown("---")

    # ── Шаг 3: Доп. расходы и финансы ───────────────────────────────────────
    if selected_items:
        with st.expander("💼 Дополнительные расходы", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                extra_delivery = st.number_input("Доставка, ₽",          min_value=0, step=1000, value=0, key="ex_del")
                extra_trash    = st.number_input("Вывоз мусора, ₽",       min_value=0, step=1000, value=0, key="ex_tr")
            with c2:
                extra_unf_pct  = st.number_input("Непредвиденные, %",     min_value=0, max_value=20, step=1, value=3, key="ex_unf")
                extra_cover    = st.number_input("Укрывные работы, ₽",    min_value=0, step=500,  value=0, key="ex_cov")
            with c3:
                extra_elec     = st.number_input("Врем. электроснабж., ₽",min_value=0, step=500,  value=0, key="ex_el")
                extra_water    = st.number_input("Врем. водоснабж., ₽",   min_value=0, step=500,  value=0, key="ex_wt")

        with st.expander("📊 Финансовые параметры", expanded=True):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                overhead_pct = st.number_input("Накладные, %", min_value=0, max_value=50, step=1, value=10, key="fin_oh")
            with fc2:
                profit_pct   = st.number_input("Прибыль, %",  min_value=0, max_value=50, step=1, value=5,  key="fin_pr")
            with fc3:
                vat_on = st.checkbox("НДС 22%", value=False, key="fin_vat")

        fin_settings = {"overhead_pct": int(overhead_pct), "profit_pct": int(profit_pct), "vat": vat_on}
        st.markdown("---")

    # ── Итог ─────────────────────────────────────────────────────────────────
    if selected_items and any(quantities.get(i["id"], 0) > 0 for i in selected_items):
        st.subheader("Шаг 3 — Итог")

        total_work = total_mat = 0.0
        rows_prev = []
        for item in selected_items:
            qty = quantities.get(item["id"], 0)
            ws = sum(qty * w.get("norm",1) * w.get("price",0) for w in item.get("works", []))
            ms = sum(qty * m.get("norm",0) * m.get("price",0) for m in item.get("materials", []))
            total_work += ws; total_mat += ms
            rows_prev.append({
                "Раздел": item["section"], "Позиция": item["name"],
                "Ед.": item["unit"], "Кол-во": qty,
                "Работы, ₽": int(ws), "Материалы, ₽": int(ms), "Итого, ₽": int(ws+ms),
            })

        try:
            base = total_work + total_mat
            unforeseen = base * extra_unf_pct / 100
            extra_total = extra_delivery + extra_trash + extra_cover + extra_elec + extra_water + unforeseen
        except Exception:
            unforeseen = extra_total = 0.0

        subtotal = total_work + total_mat + extra_total
        try:
            overhead_sum = subtotal * fin_settings["overhead_pct"] / 100
            profit_sum   = subtotal * fin_settings["profit_pct"]   / 100
        except Exception:
            overhead_sum = profit_sum = 0.0
        tbv = subtotal + overhead_sum + profit_sum
        vat_sum = tbv * 0.22 if fin_settings.get("vat") else 0.0
        grand = tbv + vat_sum

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Работы",       f"{int(total_work):,} ₽".replace(",", " "))
        m2.metric("Материалы",    f"{int(total_mat):,} ₽".replace(",", " "))
        m3.metric("Доп. расходы", f"{int(extra_total):,} ₽".replace(",", " "))
        m4.metric("ИТОГО",        f"{int(grand):,} ₽".replace(",", " "))

        import pandas as pd
        st.dataframe(pd.DataFrame(rows_prev), use_container_width=True, hide_index=True)
        st.markdown("---")

        bc1, bc2 = st.columns([1, 3])
        with bc1:
            if st.button("📥 Сформировать Excel", type="primary", use_container_width=True, key="gen_excel"):
                try:
                    extra_costs = {
                        "Доставка материалов": extra_delivery,
                        "Вывоз строительного мусора": extra_trash,
                        "Укрывные работы": extra_cover,
                        "Временное электроснабжение": extra_elec,
                        "Временное водоснабжение": extra_water,
                        f"Непредвиденные ({extra_unf_pct}%)": int(unforeseen),
                    }
                    excel_bytes = generate_excel(
                        client=client, address=address, obj_name=obj_name,
                        area=area_obj, proj_date=proj_date, manager=manager,
                        selected_items=selected_items, quantities=quantities,
                        extra_costs=extra_costs, fin_settings=fin_settings,
                    )
                    safe = re.sub(r'[^\w]', '_', client) or "КП"
                    fname = f"КП_{safe}_{proj_date}.xlsx"
                    st.session_state["excel_ready"]    = True
                    st.session_state["excel_bytes"]    = excel_bytes
                    st.session_state["excel_filename"] = fname

                    # Сохраняем в историю
                    record = {
                        "id": uuid.uuid4().hex[:8],
                        "date": str(proj_date),
                        "client": client or "—",
                        "address": address or "—",
                        "obj_name": obj_name or "—",
                        "total": int(grand),
                        "items_count": len(selected_items),
                        "quantities": {k: v for k, v in quantities.items() if v > 0},
                        "selected_ids": [i["id"] for i in selected_items],
                        "fin_settings": fin_settings,
                        "filename": fname,
                    }
                    st.session_state["kp_history"].append(record)
                    # Пишем в файл
                    hist_path = os.path.join(os.path.dirname(__file__), "kp_history.json")
                    try:
                        with open(hist_path, "w", encoding="utf-8") as f:
                            json.dump(st.session_state["kp_history"], f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    st.success("КП сформирован и сохранён в историю!")
                except Exception as e:
                    st.error(f"Ошибка: {e}")

        with bc2:
            if st.session_state.get("excel_ready"):
                st.download_button(
                    "⬇️ Скачать КП",
                    data=st.session_state["excel_bytes"],
                    file_name=st.session_state["excel_filename"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary", use_container_width=True, key="dl_excel",
                )

    elif not selected_items:
        st.info("👆 Выберите виды работ или воспользуйтесь 🤖 вкладкой «Загрузить ТЗ»")
    else:
        st.info("👆 Введите объёмы работ для расчёта")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — AI-РАЗБОР ТЗ
# ════════════════════════════════════════════════════════════════════════════════
with tab_tz:
    st.subheader("🤖 Загрузить ТЗ/смету — AI автоматически разберёт позиции")
    st.caption("Поддерживаемые форматы: Excel (.xlsx), PDF, Word (.docx)")

    api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    if not api_key:
        st.warning("⚠️ Добавьте ANTHROPIC_API_KEY в Streamlit Secrets для работы AI-разбора.")

    uploaded = st.file_uploader(
        "Перетащите файл ТЗ или кликните для выбора",
        type=["xlsx", "xls", "pdf", "docx"],
        key="tz_file",
    )

    if uploaded and api_key:
        if st.button("🚀 Запустить AI-разбор", type="primary"):
            with st.spinner("AI читает документ и ищет позиции справочника…"):
                try:
                    from ai_parser import extract_text, call_claude_api, match_items
                    raw_text = extract_text(uploaded.read(), uploaded.name)
                    if not raw_text.strip():
                        st.error("Не удалось извлечь текст из файла.")
                    else:
                        parsed = call_claude_api(raw_text, api_key)
                        matched = match_items(parsed, all_items_combined)
                        st.session_state["tz_matched"] = matched
                        st.success(f"AI извлёк {len(parsed)} позиций. Проверьте результат ниже.")
                except json.JSONDecodeError:
                    st.error("AI не смог вернуть корректный JSON. Попробуйте ещё раз.")
                except Exception as e:
                    st.error(f"Ошибка: {e}")

    elif uploaded and not api_key:
        st.info("Добавьте ANTHROPIC_API_KEY в секреты для запуска AI-разбора.")

    # ── Результаты разбора ───────────────────────────────────────────────────
    if st.session_state.get("tz_matched"):
        matched = st.session_state["tz_matched"]
        st.markdown("---")
        st.markdown(f"### Результат разбора ({len(matched)} позиций)")
        st.caption("🟢 — высокое совпадение | 🟡 — среднее | 🔴 — не найдено. Снимите галочку чтобы исключить позицию.")

        accepted_ids: list[str] = []
        accepted_qtys: dict = {}

        for idx, m in enumerate(matched):
            iid = m["matched_item"]["id"] if m["matched_item"] else None
            score = m["score"]
            color = "🟢" if score >= 0.6 else ("🟡" if score >= 0.35 else "🔴")

            rc1, rc2, rc3, rc4, rc5 = st.columns([0.5, 3, 3, 1.5, 1.5])
            with rc1:
                use = st.checkbox("", value=(score >= 0.35 and iid is not None), key=f"tz_use_{idx}")
            with rc2:
                st.write(f"{color} **{m['parsed_name']}**")
                st.caption(f"ТЗ: {m['parsed_unit']}")
            with rc3:
                if m["matched_item"]:
                    match_name = m["matched_item"]["name"]
                    match_sec  = m["matched_item"]["section"]
                    st.write(f"→ {match_name}")
                    st.caption(f"{match_sec} | score: {score}")
                else:
                    st.write("→ *не найдено в справочнике*")
            with rc4:
                qty_default = float(m["qty"]) if m["qty"] is not None else 0.0
                qty_val = st.number_input(
                    m["matched_item"]["unit"] if m["matched_item"] else "ед.",
                    min_value=0.0, value=qty_default, step=0.5, format="%.2f",
                    key=f"tz_qty_{idx}",
                )
            with rc5:
                # Заменить совпадение вручную
                all_names = ["— оставить —"] + [i["name"] for i in all_items_combined]
                override = st.selectbox("Заменить на:", all_names,
                                        key=f"tz_override_{idx}",
                                        label_visibility="collapsed")
                if override != "— оставить —":
                    iid = next((i["id"] for i in all_items_combined if i["name"] == override), iid)

            if use and iid:
                accepted_ids.append(iid)
                accepted_qtys[iid] = qty_val

        st.markdown("---")
        if st.button("✅ Перенести в КП (Шаг 1 → 2)", type="primary", key="tz_accept"):
            # Объединяем с уже выбранными через chain
            for iid in accepted_ids:
                st.session_state["chain_checked"].add(iid)
            for iid, qty in accepted_qtys.items():
                st.session_state["chain_qtys"][iid] = qty
            st.session_state["tz_matched"] = None
            st.success("Позиции перенесены! Перейдите на вкладку 📝 Составить КП → Шаг 2.")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — ИСТОРИЯ КП
# ════════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.subheader("📋 История сформированных КП")
    st.caption("КП сохраняются автоматически при нажатии «Сформировать Excel». История не удаляется.")

    history = st.session_state.get("kp_history", [])

    if not history:
        st.info("Здесь будут отображаться все сформированные КП. Пока истории нет.")
    else:
        st.markdown(f"Всего КП: **{len(history)}**")
        for rec in reversed(history):
            with st.expander(
                f"📄 {rec['date']} | {rec['client']} | {rec['obj_name']} | "
                f"{rec['total']:,} ₽".replace(",", " "),
                expanded=False,
            ):
                hc1, hc2 = st.columns(2)
                with hc1:
                    st.write(f"**Заказчик:** {rec['client']}")
                    st.write(f"**Адрес:** {rec['address']}")
                    st.write(f"**Объект:** {rec['obj_name']}")
                    st.write(f"**Дата:** {rec['date']}")
                with hc2:
                    st.write(f"**Итого:** {rec['total']:,} ₽".replace(",", " "))
                    st.write(f"**Позиций:** {rec['items_count']}")
                    st.write(f"**НДС:** {'да' if rec['fin_settings'].get('vat') else 'нет'}")

                # Кнопка загрузить этот КП обратно
                if st.button(f"🔄 Продолжить работу с этим КП", key=f"hist_load_{rec['id']}"):
                    # Восстанавливаем состояние
                    st.session_state["chain_checked"] = set(rec["selected_ids"])
                    st.session_state["chain_qtys"]    = rec["quantities"]
                    st.success("КП восстановлен. Перейдите на вкладку 📝 Составить КП.")
                    st.rerun()

    st.markdown("---")
    st.markdown("**ℹ️ Про постоянное хранение истории:**")
    st.info(
        "Сейчас история хранится в файле `kp_history.json` и в памяти сессии. "
        "Для надёжного хранения между разными устройствами нужно подключить Google Sheets. "
        "Инструкция: [создать Service Account в Google Cloud Console](https://console.cloud.google.com/), "
        "добавить JSON-ключ в Streamlit Secrets как `GOOGLE_SERVICE_ACCOUNT`, "
        "создать таблицу и поделиться ею с email сервисного аккаунта."
    )

st.markdown("---")
st.caption("ООО «Ремкон» · Калькулятор КП v1.3 · remkon.ru")
