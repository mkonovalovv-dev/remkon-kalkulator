# app.py — Калькулятор КП Ремкон v2.0
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

# ─── CSS: компактная таблица корзины ─────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding: 0 4px !important; }
div[data-testid="stNumberInput"] input { padding: 4px 8px !important; }
</style>
""", unsafe_allow_html=True)

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

# ─── ДАННЫЕ И STATE ───────────────────────────────────────────────────────────
all_items = load_data()

if "section_order"  not in st.session_state:
    st.session_state["section_order"]  = list(DEFAULT_SECTION_ORDER)
if "custom_items"   not in st.session_state:
    st.session_state["custom_items"]   = []
if "kp_cart"        not in st.session_state:
    st.session_state["kp_cart"]        = {}   # {item_id: {"item": ..., "qty": float}}
if "kp_history"     not in st.session_state:
    hist_path = os.path.join(os.path.dirname(__file__), "kp_history.json")
    try:
        with open(hist_path, "r", encoding="utf-8") as f:
            st.session_state["kp_history"] = json.load(f)
    except Exception:
        st.session_state["kp_history"] = []

all_items_combined = all_items + st.session_state["custom_items"]
item_map = {i["id"]: i for i in all_items_combined}

# Вспомогательные функции корзины
def cart_add(item: dict, qty: float):
    iid = item["id"]
    if iid in st.session_state["kp_cart"]:
        st.session_state["kp_cart"][iid]["qty"] += qty
    else:
        st.session_state["kp_cart"][iid] = {"item": item, "qty": qty}

def cart_remove(item_id: str):
    st.session_state["kp_cart"].pop(item_id, None)

def item_price(item: dict) -> float:
    return sum(w["price"] * w["norm"] for w in item.get("works", []))

# ─── ШАПКА ───────────────────────────────────────────────────────────────────
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
            client   = st.text_input("Заказчик",        placeholder="ООО «Пример»",    key="kp_client")
            address  = st.text_input("Адрес объекта",   placeholder="г. Москва, ул…",  key="kp_address")
        with c2:
            obj_name = st.text_input("Объект",          placeholder="Офис / склад",    key="kp_obj")
            area_obj = st.number_input("Площадь, м²",   min_value=0.0, step=1.0,       key="kp_area", format="%.1f")
            height   = st.number_input("Высота, м",     min_value=2.0, max_value=10.0,
                                       step=0.1, value=3.0, format="%.1f",             key="kp_height")
        with c3:
            proj_date = st.date_input("Дата КП", value=date.today(), key="kp_date")
            manager   = st.text_input("Менеджер",       placeholder="Имя",             key="kp_mgr")

    st.markdown("---")

    # ════════════════════════════════════════════════════
    # ГЛАВНЫЙ БЛОК: ПОИСК + КОРЗИНА
    # ════════════════════════════════════════════════════

    left_col, right_col = st.columns([5, 4], gap="large")

    # ── ЛЕВАЯ КОЛОНКА: ПОИСК ────────────────────────────────────────────────
    with left_col:
        st.subheader("🔍 Поиск работ")

        search_q = st.text_input(
            "Введите название работы",
            placeholder="Штукатурка, паркет, демонтаж плитки…",
            key="search_q",
            label_visibility="collapsed",
        )

        # Быстрые фильтры по категориям
        quick_cats = ["Все", "Демонтаж", "Стяжка", "Штукатурка", "ГКЛ", "Малярка",
                      "Плитка", "Полы", "Двери", "Электрика", "Сантехника", "Кровля"]
        selected_cat = st.pills("Быстрый фильтр:", quick_cats, default="Все", key="quick_cat")

        st.markdown("")  # отступ

        # Маппинг категорий к разделам
        CAT_MAP = {
            "Демонтаж":   ["Демонтажные работы"],
            "Стяжка":     ["Стяжка полов", "Черновые и общестроительные работы"],
            "Штукатурка": ["Штукатурные работы"],
            "ГКЛ":        ["ГКЛ (гипсокартон)", "Возведение перегородок"],
            "Малярка":    ["Малярные работы"],
            "Плитка":     ["Плиточные работы"],
            "Полы":       ["Финишные полы", "Стяжка полов"],
            "Двери":      ["Монтаж дверей"],
            "Электрика":  ["Электромонтаж (черновой)", "Финишная электрика"],
            "Сантехника": ["Сантехника (черновая)", "Финишная сантехника"],
            "Кровля":     ["Кровельные работы", "Фасадные работы"],
        }

        def filter_items(query: str, cat: str) -> list:
            q = query.strip().lower()
            cat_sections = CAT_MAP.get(cat, [])
            results = []
            for item in all_items_combined:
                # Фильтр по категории
                if cat != "Все" and item["section"] not in cat_sections:
                    continue
                # Фильтр по строке поиска
                if q:
                    searchable = (item["name"] + " " + item["section"] + " " +
                                  (item.get("subsection") or "")).lower()
                    if not all(word in searchable for word in q.split()):
                        continue
                results.append(item)
            return results

        results = filter_items(search_q, selected_cat)

        # Если нет запроса и нет фильтра — показываем подсказку
        if not search_q.strip() and selected_cat == "Все":
            st.info("Введите название работы или выберите категорию выше")

            # Показываем цепочки-мастера как быстрый старт
            st.markdown("**⚡ Быстрый старт — мастер расчёта:**")
            chain_cols = st.columns(3)
            for ci, (sec_name, chain_def) in enumerate(CHAINS.items()):
                with chain_cols[ci % 3]:
                    if st.button(
                        f"{chain_def['emoji']} {sec_name.split('(')[0].strip()}",
                        key=f"quick_chain_{ci}",
                        use_container_width=True,
                    ):
                        st.session_state["active_chain"] = sec_name
                        st.rerun()
        else:
            # Показываем результаты
            MAX_RESULTS = 30
            total_found = len(results)
            if total_found == 0:
                st.warning("Позиций не найдено. Попробуйте другое слово.")
                if st.button("➕ Добавить новую позицию в справочник", key="add_new_from_search"):
                    st.session_state["show_add_custom"] = True
            else:
                st.caption(f"Найдено: {total_found} позиций{' (показаны первые 30)' if total_found > MAX_RESULTS else ''}")

                for item in results[:MAX_RESULTS]:
                    iid = item["id"]
                    in_cart = iid in st.session_state["kp_cart"]
                    price = item_price(item)

                    rc1, rc2, rc3, rc4 = st.columns([0.4, 5, 2, 1.2])
                    with rc1:
                        st.markdown("✅" if in_cart else "⬜")
                    with rc2:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"{item['section']}  ·  {item.get('subsection', '')}")
                    with rc3:
                        qty_key = f"sq_{iid}"
                        current_cart_qty = st.session_state["kp_cart"].get(iid, {}).get("qty", 1.0)
                        qty = st.number_input(
                            item["unit"],
                            min_value=0.0,
                            value=current_cart_qty if in_cart else 1.0,
                            step=1.0, format="%.1f",
                            key=qty_key,
                            label_visibility="visible",
                        )
                    with rc4:
                        st.markdown(f"*{price:,.0f} ₽*")
                        if in_cart:
                            if st.button("✖ Убрать", key=f"rm_s_{iid}", use_container_width=True):
                                cart_remove(iid)
                                st.rerun()
                        else:
                            if st.button("➕ Добавить", key=f"add_s_{iid}", use_container_width=True, type="primary"):
                                cart_add(item, qty)
                                st.rerun()

        # ── Мастер расчёта цепочек ───────────────────────────────────────
        active_chain = st.session_state.get("active_chain")
        if active_chain and active_chain in CHAINS:
            st.markdown("---")
            chain_def = CHAINS[active_chain]
            st.markdown(f"#### {chain_def['emoji']} Мастер: {chain_def['label']}")

            inp_vals = {}
            inp_cols = st.columns(min(len(chain_def["inputs"]), 3))
            for i, inp in enumerate(chain_def["inputs"]):
                if inp.get("advanced"):
                    inp_vals[inp["id"]] = inp["default"]
                    continue
                with inp_cols[i % len(inp_cols)]:
                    inp_vals[inp["id"]] = st.number_input(
                        f"{inp['label']}, {inp['unit']}",
                        min_value=0.0, value=float(inp["default"]),
                        step=0.5, format="%.2f",
                        key=f"ch_inp_{active_chain}_{inp['id']}",
                    )

            computed_vals = dict(inp_vals)
            if chain_def.get("computed"):
                st.markdown("**📐 Объёмы:**")
                cv_cols = st.columns(min(len(chain_def["computed"]), 4))
                for ci2, (cid, (expr, unit, clabel)) in enumerate(chain_def["computed"].items()):
                    try:
                        val = eval(expr, {"__builtins__": {}},
                                   {**computed_vals, "max": max, "min": min, "round": round})
                    except Exception:
                        val = 0.0
                    computed_vals[cid] = val
                    with cv_cols[ci2 % len(cv_cols)]:
                        st.metric(clabel, f"{val} {unit}")

            chain_matches = find_chain_items(chain_def, all_items_combined)
            if chain_matches:
                st.markdown("**📋 Добавить в КП:**")
                for match in chain_matches:
                    item = match["item"]
                    qty_id = match["qty_id"]
                    note = match["note"]
                    qty_val = float(computed_vals.get(qty_id, 0.0)) if qty_id else 1.0
                    iid = item["id"]

                    cm1, cm2, cm3, cm4 = st.columns([0.4, 5, 2, 1.5])
                    in_cart = iid in st.session_state["kp_cart"]
                    with cm1:
                        st.markdown("✅" if in_cart else "⬜")
                    with cm2:
                        price = item_price(item)
                        st.write(f"**{item['name']}** — {price:,.0f} ₽/{item['unit']}")
                        st.caption(f"{item['section']}  {'('+note+')' if note else ''}")
                    with cm3:
                        chain_qty = st.number_input(
                            item["unit"], min_value=0.0, value=qty_val,
                            step=0.5, format="%.2f",
                            key=f"ch_qty_{active_chain}_{iid}",
                        )
                    with cm4:
                        if in_cart:
                            if st.button("✖ Убрать", key=f"ch_rm_{active_chain}_{iid}", use_container_width=True):
                                cart_remove(iid)
                                st.rerun()
                        else:
                            if st.button("➕ В КП", key=f"ch_add_{active_chain}_{iid}",
                                         use_container_width=True, type="primary"):
                                cart_add(item, chain_qty)
                                st.rerun()

            if st.button("✖ Закрыть мастер", key="close_chain"):
                st.session_state["active_chain"] = None
                st.rerun()

        # ── Добавление своей позиции ─────────────────────────────────────
        if st.session_state.get("show_add_custom"):
            st.markdown("---")
            st.markdown("**➕ Своя позиция:**")
            nc1, nc2, nc3, nc4 = st.columns([3, 1.2, 1.2, 1.5])
            with nc1: new_name = st.text_input("Название", key="cust_name")
            with nc2: new_unit = st.text_input("Ед.", value="кв.м.", key="cust_unit")
            with nc3: new_price = st.number_input("Цена ₽/ед.", min_value=0, step=100, key="cust_price")
            with nc4: new_sec = st.selectbox("Раздел", st.session_state["section_order"], key="cust_sec")
            if st.button("✅ Добавить в справочник и КП", type="primary", key="cust_save"):
                if new_name.strip():
                    ni = {
                        "id": f"custom_{uuid.uuid4().hex[:8]}",
                        "section": new_sec,
                        "subsection": "Пользовательские позиции",
                        "name": new_name.strip(),
                        "unit": new_unit.strip() or "шт.",
                        "works": [{"name": new_name.strip(), "unit": new_unit.strip() or "шт.",
                                   "price": int(new_price), "norm": 1.0}],
                        "materials": [],
                    }
                    st.session_state["custom_items"].append(ni)
                    all_items_combined = all_items + st.session_state["custom_items"]
                    cart_add(ni, 1.0)
                    st.session_state["show_add_custom"] = False
                    st.rerun()

    # ── ПРАВАЯ КОЛОНКА: КОРЗИНА КП ───────────────────────────────────────────
    with right_col:
        cart = st.session_state["kp_cart"]
        n_cart = len(cart)

        # Подсчёт итогов
        total_work = total_mat = 0.0
        for entry in cart.values():
            it = entry["item"]
            q  = entry["qty"]
            total_work += sum(q * w.get("norm",1)*w.get("price",0) for w in it.get("works",[]))
            total_mat  += sum(q * m.get("norm",0)*m.get("price",0) for m in it.get("materials",[]))

        # Заголовок корзины
        if n_cart > 0:
            st.subheader(f"🛒 КП ({n_cart} поз.)")
            m1, m2 = st.columns(2)
            m1.metric("Работы", f"{int(total_work):,} ₽".replace(",", " "))
            m2.metric("Материалы", f"{int(total_mat):,} ₽".replace(",", " "))

            st.markdown("---")

            # Список позиций в корзине
            rows_for_excel = []
            for iid, entry in list(cart.items()):
                it  = entry["item"]
                qty = entry["qty"]
                ws  = sum(qty * w.get("norm",1)*w.get("price",0) for w in it.get("works",[]))
                ms  = sum(qty * m.get("norm",0)*m.get("price",0) for m in it.get("materials",[]))
                rows_for_excel.append({"Раздел": it["section"], "Позиция": it["name"],
                                       "Ед.": it["unit"], "Кол-во": qty,
                                       "Работы, ₽": int(ws), "Материалы, ₽": int(ms),
                                       "Итого, ₽": int(ws+ms)})

                bc1, bc2, bc3, bc4 = st.columns([4, 1.5, 1.5, 0.7])
                with bc1:
                    st.markdown(f"**{it['name']}**")
                    st.caption(f"{it['section']}")
                with bc2:
                    new_qty = st.number_input(
                        it["unit"], min_value=0.0, value=float(qty),
                        step=1.0, format="%.1f",
                        key=f"cart_qty_{iid}",
                        label_visibility="visible",
                    )
                    if abs(new_qty - qty) > 0.001:
                        st.session_state["kp_cart"][iid]["qty"] = new_qty
                        st.rerun()
                with bc3:
                    st.markdown(f"**{int(ws+ms):,} ₽**".replace(",", " "))
                with bc4:
                    if st.button("✖", key=f"rm_c_{iid}", help="Убрать из КП"):
                        cart_remove(iid)
                        st.rerun()

            st.markdown("---")

            # Финансовые параметры
            with st.expander("💼 Доп. расходы и финансы", expanded=False):
                e1, e2 = st.columns(2)
                with e1:
                    extra_delivery = st.number_input("Доставка, ₽",        min_value=0, step=1000, value=0, key="ex_del")
                    extra_trash    = st.number_input("Вывоз мусора, ₽",    min_value=0, step=1000, value=0, key="ex_tr")
                    extra_unf_pct  = st.number_input("Непредвиденные, %",  min_value=0, max_value=20, step=1, value=3, key="ex_unf")
                with e2:
                    overhead_pct   = st.number_input("Накладные, %",       min_value=0, max_value=50, step=1, value=10, key="fin_oh")
                    profit_pct     = st.number_input("Прибыль, %",         min_value=0, max_value=50, step=1, value=5,  key="fin_pr")
                    vat_on         = st.checkbox("НДС 22%", value=False, key="fin_vat")

            # Финальный расчёт
            base = total_work + total_mat
            try:
                unforeseen   = base * extra_unf_pct / 100
                extra_total  = extra_delivery + extra_trash + unforeseen
                overhead_sum = (base + extra_total) * overhead_pct / 100
                profit_sum   = (base + extra_total) * profit_pct   / 100
                tbv          = base + extra_total + overhead_sum + profit_sum
                vat_sum      = tbv * 0.22 if vat_on else 0.0
                grand        = tbv + vat_sum
            except Exception:
                grand = base

            st.metric("**ИТОГО по КП**", f"{int(grand):,} ₽".replace(",", " "))

            # Кнопки
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button("📥 Сформировать Excel", type="primary",
                             use_container_width=True, key="gen_excel"):
                    try:
                        fin_settings = {
                            "overhead_pct": int(overhead_pct),
                            "profit_pct":   int(profit_pct),
                            "vat":          vat_on,
                        }
                        extra_costs = {
                            "Доставка":               extra_delivery,
                            "Вывоз мусора":           extra_trash,
                            f"Непредвиденные ({extra_unf_pct}%)": int(unforeseen),
                        }
                        selected_items_ex = [e["item"] for e in cart.values()]
                        quantities_ex     = {iid: e["qty"] for iid, e in cart.items()}

                        excel_bytes = generate_excel(
                            client=client, address=address, obj_name=obj_name,
                            area=area_obj, proj_date=proj_date, manager=manager,
                            selected_items=selected_items_ex, quantities=quantities_ex,
                            extra_costs=extra_costs, fin_settings=fin_settings,
                        )
                        safe = re.sub(r'[^\w]', '_', client) or "КП"
                        fname = f"КП_{safe}_{proj_date}.xlsx"
                        st.session_state["excel_ready"]    = True
                        st.session_state["excel_bytes"]    = excel_bytes
                        st.session_state["excel_filename"] = fname

                        # История
                        record = {
                            "id": uuid.uuid4().hex[:8], "date": str(proj_date),
                            "client": client or "—", "address": address or "—",
                            "obj_name": obj_name or "—", "total": int(grand),
                            "items_count": len(cart),
                            "cart_snapshot": {
                                iid: {"item_id": iid, "name": e["item"]["name"],
                                      "qty": e["qty"]}
                                for iid, e in cart.items()
                            },
                            "fin_settings": fin_settings, "filename": fname,
                        }
                        st.session_state["kp_history"].append(record)
                        hist_path = os.path.join(os.path.dirname(__file__), "kp_history.json")
                        try:
                            with open(hist_path, "w", encoding="utf-8") as f:
                                json.dump(st.session_state["kp_history"], f,
                                          ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        st.success("КП сформирован!")
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

            with btn2:
                if st.session_state.get("excel_ready"):
                    st.download_button(
                        "⬇️ Скачать",
                        data=st.session_state["excel_bytes"],
                        file_name=st.session_state["excel_filename"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="secondary", use_container_width=True, key="dl_excel",
                    )

            st.markdown("---")
            if st.button("🗑 Очистить КП", use_container_width=True, key="clear_cart"):
                st.session_state["kp_cart"] = {}
                st.session_state["excel_ready"] = False
                st.rerun()

        else:
            st.subheader("🛒 КП")
            st.info("Найдите работы слева и нажмите ➕ Добавить")
            st.markdown("Или запустите **мастер расчёта** — он автоматически подберёт всю цепочку работ с объёмами.")

    st.markdown("---")

    # ── Конструктор (расширенный режим) ─────────────────────────────────────
    with st.expander("🔧 Конструктор: создать раздел или свою позицию", expanded=False):
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
            st.caption("streamlit-sortables не установлен — порядок через ▲▼")
            so = st.session_state["section_order"]
            for idx, sec in enumerate(so):
                cu, cd, cn = st.columns([0.5, 0.5, 8])
                with cu:
                    if idx > 0 and st.button("▲", key=f"up_{idx}"):
                        so[idx-1], so[idx] = so[idx], so[idx-1]; st.rerun()
                with cd:
                    if idx < len(so)-1 and st.button("▼", key=f"dn_{idx}"):
                        so[idx], so[idx+1] = so[idx+1], so[idx]; st.rerun()
                with cn:
                    st.write(sec)

        st.markdown("---")
        st.markdown("**Новый раздел:**")
        ns1, ns2 = st.columns([4, 1.5])
        with ns1:
            new_sec_name = st.text_input("Название раздела", key="new_sec_name",
                                         label_visibility="collapsed",
                                         placeholder="Например: Благоустройство")
        with ns2:
            if st.button("Создать ➕", type="primary", use_container_width=True):
                name = new_sec_name.strip()
                if name and name not in st.session_state["section_order"]:
                    st.session_state["section_order"].append(name)
                    st.rerun()

        if st.button("🔄 Сбросить порядок к стандартному"):
            st.session_state["section_order"] = list(DEFAULT_SECTION_ORDER)
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — AI-РАЗБОР ТЗ
# ════════════════════════════════════════════════════════════════════════════════
with tab_tz:
    st.subheader("🤖 Загрузить ТЗ — AI разберёт и перенесёт в КП")
    st.caption("Форматы: Excel (.xlsx), PDF, Word (.docx)")

    api_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))

    uploaded = st.file_uploader(
        "Перетащите файл ТЗ",
        type=["xlsx", "xls", "pdf", "docx"],
        key="tz_file",
    )

    if uploaded and api_key:
        if st.button("🚀 Запустить AI-разбор", type="primary"):
            with st.spinner("Читаю документ и ищу позиции…"):
                try:
                    from ai_parser import extract_text, call_claude_api, match_items
                    raw_text = extract_text(uploaded.read(), uploaded.name)
                    if not raw_text.strip():
                        st.error("Не удалось извлечь текст.")
                    else:
                        parsed  = call_claude_api(raw_text, api_key)
                        matched = match_items(parsed, all_items_combined)
                        st.session_state["tz_matched"] = matched
                        st.success(f"AI извлёк {len(parsed)} позиций. Проверьте ниже.")
                except json.JSONDecodeError:
                    st.error("AI вернул некорректный JSON. Попробуйте ещё раз.")
                except Exception as e:
                    st.error(f"Ошибка: {e}")
    elif not uploaded:
        st.info("Загрузите файл ТЗ")

    if st.session_state.get("tz_matched"):
        matched = st.session_state["tz_matched"]
        st.markdown("---")
        st.markdown(f"### Результат ({len(matched)} позиций)")
        st.caption("🟢 высокое совпадение · 🟡 среднее · 🔴 не найдено")

        for idx, m in enumerate(matched):
            iid     = m["matched_item"]["id"] if m["matched_item"] else None
            score   = m["score"]
            color   = "🟢" if score >= 0.6 else ("🟡" if score >= 0.35 else "🔴")
            in_cart = iid in st.session_state["kp_cart"] if iid else False

            mc1, mc2, mc3, mc4, mc5 = st.columns([0.5, 3.5, 3, 1.5, 1.5])
            with mc1:
                use = st.checkbox("", value=(score >= 0.35 and iid is not None),
                                  key=f"tz_use_{idx}")
            with mc2:
                st.write(f"{color} **{m['parsed_name']}**")
                st.caption(f"ТЗ: {m['parsed_unit']}")
            with mc3:
                if m["matched_item"]:
                    st.write(f"→ {m['matched_item']['name']}")
                    st.caption(f"{m['matched_item']['section']} | score: {score}")
                else:
                    st.write("→ *нет в справочнике*")
                # Возможность заменить матч
                override_names = ["— оставить —"] + [i["name"] for i in all_items_combined[:200]]
                override = st.selectbox("", override_names, key=f"tz_ov_{idx}",
                                        label_visibility="collapsed")
                if override != "— оставить —":
                    iid = next((i["id"] for i in all_items_combined if i["name"] == override), iid)
            with mc4:
                qty_default = float(m["qty"]) if m["qty"] else 0.0
                qty_val = st.number_input(
                    m["matched_item"]["unit"] if m["matched_item"] else "ед.",
                    min_value=0.0, value=qty_default, step=0.5, format="%.2f",
                    key=f"tz_qty_{idx}",
                )
            with mc5:
                if in_cart:
                    st.markdown("✅ в КП")
                else:
                    if use and iid:
                        it = item_map.get(iid)
                        if it and st.button("➕ В КП", key=f"tz_add_{idx}", use_container_width=True):
                            cart_add(it, qty_val)
                            st.rerun()

        st.markdown("---")
        if st.button("✅ Добавить все отмеченные в КП", type="primary", key="tz_accept_all"):
            for idx, m in enumerate(matched):
                use_key = f"tz_use_{idx}"
                qty_key = f"tz_qty_{idx}"
                ov_key  = f"tz_ov_{idx}"
                if st.session_state.get(use_key, False):
                    iid = m["matched_item"]["id"] if m["matched_item"] else None
                    ov  = st.session_state.get(ov_key, "— оставить —")
                    if ov != "— оставить —":
                        iid = next((i["id"] for i in all_items_combined if i["name"] == ov), iid)
                    qty = st.session_state.get(qty_key, 0.0)
                    if iid and qty > 0:
                        it = item_map.get(iid)
                        if it:
                            cart_add(it, qty)
            st.session_state["tz_matched"] = None
            st.success("Позиции добавлены! Перейдите в 📝 Составить КП.")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — ИСТОРИЯ КП
# ════════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.subheader("📋 История КП")
    st.caption("Каждый сформированный Excel автоматически сохраняется. История не удаляется.")

    history = st.session_state.get("kp_history", [])
    if not history:
        st.info("История пуста — сформируйте первый КП.")
    else:
        st.markdown(f"Всего КП: **{len(history)}**")
        for rec in reversed(history):
            total_fmt = f"{rec['total']:,} ₽".replace(",", " ")
            with st.expander(
                f"📄 {rec['date']}  |  {rec['client']}  |  {rec['obj_name']}  |  {total_fmt}",
                expanded=False,
            ):
                hc1, hc2 = st.columns(2)
                with hc1:
                    st.write(f"**Заказчик:** {rec['client']}")
                    st.write(f"**Адрес:** {rec['address']}")
                    st.write(f"**Объект:** {rec['obj_name']}")
                    st.write(f"**Дата:** {rec['date']}")
                with hc2:
                    st.write(f"**Итого:** {total_fmt}")
                    st.write(f"**Позиций:** {rec['items_count']}")
                    st.write(f"**НДС:** {'да' if rec['fin_settings'].get('vat') else 'нет'}")

                if st.button("🔄 Восстановить этот КП", key=f"hist_load_{rec['id']}"):
                    new_cart = {}
                    for iid, snap in rec.get("cart_snapshot", {}).items():
                        it = item_map.get(iid)
                        if it:
                            new_cart[iid] = {"item": it, "qty": snap["qty"]}
                    st.session_state["kp_cart"] = new_cart
                    st.success("КП восстановлен. Перейдите в 📝 Составить КП.")
                    st.rerun()

    st.markdown("---")
    st.info(
        "Для хранения истории на Streamlit Cloud: добавьте Google Service Account "
        "в Streamlit Secrets → подключим Google Sheets."
    )

st.markdown("---")
st.caption("ООО «Ремкон» · Калькулятор КП v2.0 · remkon.ru")
