# app.py — Калькулятор КП Ремкон v2.1
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

# ─── ДИЗАЙН-СИСТЕМА ──────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
.main .block-container { max-width: 1300px; padding: 1.5rem 2rem; }
.main { background: #F8FAFC; }

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── App header ── */
.app-header {
    background: linear-gradient(135deg, #0F2744 0%, #1D4ED8 100%);
    padding: 22px 32px; border-radius: 16px; margin-bottom: 8px;
    display: flex; align-items: center; justify-content: space-between;
}
.app-header-left h1 {
    font-size: 26px; font-weight: 800; color: white; margin: 0; letter-spacing: -0.5px;
}
.app-header-left p {
    font-size: 13px; color: rgba(255,255,255,0.65); margin: 4px 0 0;
}
.app-header-badge {
    background: rgba(255,255,255,0.15); color: white;
    padding: 4px 12px; border-radius: 999px; font-size: 12px;
    font-weight: 600; border: 1px solid rgba(255,255,255,0.25);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0; background: #E2E8F0; border-radius: 12px; padding: 4px;
    margin-bottom: 16px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px; padding: 9px 24px; font-size: 14px; font-weight: 600;
    color: #64748B; background: transparent; border: none; transition: all 0.2s;
}
.stTabs [aria-selected="true"] {
    background: white !important; color: #1D4ED8 !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.1);
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }

/* ── Upload hero ── */
.upload-hero {
    background: linear-gradient(135deg, #0F2744 0%, #1E40AF 50%, #3B82F6 100%);
    border-radius: 20px; padding: 52px 40px; text-align: center; color: white;
    margin: 8px 0 24px;
}
.upload-hero h2 { font-size: 30px; font-weight: 800; margin: 0 0 10px; color: white; letter-spacing: -0.5px; }
.upload-hero p { font-size: 16px; color: rgba(255,255,255,0.75); margin: 0 0 28px; }
.format-chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 8px; }
.format-chip {
    background: rgba(255,255,255,0.15); color: white;
    padding: 5px 14px; border-radius: 999px; font-size: 13px; font-weight: 500;
    border: 1px solid rgba(255,255,255,0.3);
}

/* ── Status badges ── */
.badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;
    letter-spacing: 0.3px;
}
.badge-green  { background: #DCFCE7; color: #14532D; }
.badge-yellow { background: #FEF9C3; color: #713F12; }
.badge-red    { background: #FEE2E2; color: #7F1D1D; }
.badge-orange { background: #FFEDD5; color: #7C2D12; }
.badge-blue   { background: #DBEAFE; color: #1E3A8A; }

/* ── Result section header ── */
.sec-header {
    background: #1E293B; color: white; padding: 7px 16px;
    border-radius: 8px; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase; margin: 20px 0 8px;
    display: flex; align-items: center; gap: 8px;
}

/* ── Result card ── */
.r-card {
    background: white; border-radius: 10px; padding: 14px 18px;
    margin: 5px 0; border: 1px solid #E2E8F0;
    transition: box-shadow 0.15s, border-color 0.15s;
}
.r-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.07); border-color: #CBD5E1; }
.r-card.match-ok  { border-left: 3px solid #10B981; }
.r-card.match-mid { border-left: 3px solid #F59E0B; }
.r-card.match-no  { border-left: 3px solid #EF4444; background: #FFF8F8; }
.r-card.modified  { border-left: 3px solid #F59E0B; background: #FFFBEB; }
.r-card.added     { border-left: 3px solid #10B981; background: #F0FDF4; }
.r-card.removed   { border-left: 3px solid #EF4444; background: #FFF5F5; opacity: 0.7; }
.r-name  { font-weight: 700; font-size: 14px; color: #0F172A; }
.r-sub   { font-size: 12px; color: #64748B; margin-top: 3px; }
.r-note  { font-size: 12px; color: #F59E0B; font-weight: 600; margin-top: 4px; }

/* ── Stats bar ── */
.stats-bar {
    display: flex; gap: 16px; background: white; border-radius: 12px;
    padding: 16px 24px; border: 1px solid #E2E8F0; margin: 16px 0;
    flex-wrap: wrap;
}
.stat-item { text-align: center; }
.stat-value { font-size: 22px; font-weight: 800; color: #0F172A; }
.stat-label { font-size: 11px; color: #94A3B8; font-weight: 600;
              letter-spacing: 0.5px; text-transform: uppercase; margin-top: 2px; }

/* ── Cart item ── */
.cart-item {
    background: white; border-radius: 10px; padding: 12px 16px;
    border: 1px solid #E2E8F0; margin: 4px 0;
}

/* ── Summary metric ── */
.sum-metric {
    background: linear-gradient(135deg, #0F2744, #1D4ED8);
    color: white; border-radius: 14px; padding: 20px 24px; text-align: center;
}
.sum-metric .val { font-size: 28px; font-weight: 800; color: white; }
.sum-metric .lbl { font-size: 12px; color: rgba(255,255,255,0.7); margin-top: 4px; font-weight: 600; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 10px; font-weight: 600; transition: all 0.2s;
    border: 1px solid transparent;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1D4ED8, #3B82F6);
    border: none; color: white; box-shadow: 0 2px 8px rgba(59,130,246,0.35);
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px); box-shadow: 0 4px 16px rgba(59,130,246,0.45);
}
.stButton > button[kind="secondary"] {
    background: white; border-color: #CBD5E1; color: #374151;
}
.stButton > button[kind="secondary"]:hover { border-color: #3B82F6; color: #1D4ED8; }

/* ── Progress bar ── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #1D4ED8, #3B82F6) !important;
    border-radius: 999px;
}

/* ── File uploader inside hero ── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.08) !important;
    border: 2px dashed rgba(255,255,255,0.4) !important;
    border-radius: 12px !important; transition: all 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(255,255,255,0.7) !important;
    background: rgba(255,255,255,0.12) !important;
}
[data-testid="stFileUploader"] label { color: white !important; }
[data-testid="stFileUploaderDropzoneInput"] + div { color: rgba(255,255,255,0.8) !important; }

/* ── Compact rows ── */
div[data-testid="stHorizontalBlock"] > div { padding: 0 4px !important; }
div[data-testid="stNumberInput"] input { padding: 4px 8px !important; }

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #F8FAFC !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 14px !important;
    border: 1px solid #E2E8F0 !important;
}

/* ── Success / Error messages ── */
.stSuccess { border-radius: 10px !important; }
.stError   { border-radius: 10px !important; }
.stWarning { border-radius: 10px !important; }
.stInfo    { border-radius: 10px !important; }
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
if "suggest_for"    not in st.session_state:
    st.session_state["suggest_for"]    = None  # item_id для которого показываем попап
if "suggest_qty"    not in st.session_state:
    st.session_state["suggest_qty"]    = {}    # {item_id: qty} для попапа
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
def cart_add(item: dict, qty: float, trigger_suggest: bool = True):
    iid = item["id"]
    if iid in st.session_state["kp_cart"]:
        st.session_state["kp_cart"][iid]["qty"] += qty
    else:
        st.session_state["kp_cart"][iid] = {"item": item, "qty": qty}
    # Проверяем есть ли цепочки для этой позиции — запускаем попап
    if trigger_suggest:
        section = item.get("section", "")
        if section in CHAINS:
            chain_matches = find_chain_items(CHAINS[section], all_items_combined)
            # Оставляем только те которых ещё нет в корзине
            new_suggestions = [m for m in chain_matches
                               if m["item"]["id"] != iid
                               and m["item"]["id"] not in st.session_state["kp_cart"]]
            if new_suggestions:
                st.session_state["suggest_for"] = iid
                st.session_state["suggest_qty"] = qty

def cart_remove(item_id: str):
    st.session_state["kp_cart"].pop(item_id, None)
    if st.session_state.get("suggest_for") == item_id:
        st.session_state["suggest_for"] = None

def item_price(item: dict) -> float:
    return sum(w["price"] * w["norm"] for w in item.get("works", []))

# ─── ШАПКА ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-header-left">
    <h1>🏗️ Ремкон · Калькулятор КП</h1>
    <p>Система формирования коммерческих предложений · 02.06.2026 · Безналичный расчёт</p>
  </div>
  <div>
    <span class="app-header-badge">НДС 22%</span>&nbsp;
    <span class="app-header-badge">v2.1</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ТЗ — первая вкладка (основной поток работы)
tab_tz, tab_kp, tab_hist = st.tabs(["🤖 Разбор ТЗ", "🛒 Конструктор КП", "📋 История"])


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

        # ── Попап сопутствующих работ ────────────────────────────────────
        suggest_id = st.session_state.get("suggest_for")
        if suggest_id and suggest_id in st.session_state["kp_cart"]:
            trigger_item = st.session_state["kp_cart"][suggest_id]["item"]
            trigger_qty  = st.session_state["suggest_qty"]
            section      = trigger_item.get("section", "")

            if section in CHAINS:
                chain_def    = CHAINS[section]
                chain_matches = find_chain_items(chain_def, all_items_combined)
                suggestions  = [m for m in chain_matches
                                if m["item"]["id"] != suggest_id
                                and m["item"]["id"] not in st.session_state["kp_cart"]]

                if suggestions:
                    st.markdown("---")
                    st.markdown(
                        f"💡 **К «{trigger_item['name']}» обычно добавляют:**"
                    )
                    with st.container():
                        for m in suggestions:
                            sit   = m["item"]
                            siid  = sit["id"]
                            note  = m["note"]
                            # Предлагаем тот же объём что у основной позиции
                            s_qty = float(trigger_qty) if trigger_qty else 1.0

                            sc1, sc2, sc3, sc4 = st.columns([0.5, 5, 1.8, 1.5])
                            with sc1:
                                add_it = st.checkbox("", value=True, key=f"sug_chk_{siid}")
                            with sc2:
                                s_price = item_price(sit)
                                st.write(f"**{sit['name']}** — {s_price:,.0f} ₽/{sit['unit']}")
                                st.caption(f"{sit['section']}  {'('+note+')' if note else ''}")
                            with sc3:
                                s_qty_in = st.number_input(
                                    sit["unit"], min_value=0.0, value=s_qty,
                                    step=1.0, format="%.1f",
                                    key=f"sug_qty_{siid}",
                                )
                            with sc4:
                                st.write(f"*{s_price * s_qty_in:,.0f} ₽*")

                        scb1, scb2 = st.columns([2, 2])
                        with scb1:
                            if st.button("✅ Добавить выбранные", type="primary",
                                         key="sug_accept", use_container_width=True):
                                for m in suggestions:
                                    siid = m["item"]["id"]
                                    if st.session_state.get(f"sug_chk_{siid}", False):
                                        q = st.session_state.get(f"sug_qty_{siid}", 1.0)
                                        cart_add(m["item"], q, trigger_suggest=False)
                                st.session_state["suggest_for"] = None
                                st.rerun()
                        with scb2:
                            if st.button("Пропустить →", key="sug_skip",
                                         use_container_width=True):
                                st.session_state["suggest_for"] = None
                                st.rerun()
                    st.markdown("---")
                else:
                    st.session_state["suggest_for"] = None

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

                # ── Блок материалов ──────────────────────────────────────────
                mat_key  = f"mat_{iid}"
                chat_key = f"mat_chat_{iid}"
                if mat_key not in st.session_state:
                    # Авто-загрузка материалов из справочника при первом открытии
                    default_mats = []
                    for m in it.get("materials", []):
                        norm  = m.get("norm", 0)
                        cp    = m.get("price", 0)      # цена в справочнике = клиентская
                        pp    = int(cp / 1.2)           # расчётная закупочная ~80%
                        total_q = round(norm * float(qty), 2)
                        default_mats.append({
                            "key":          "",
                            "name":         m.get("name", ""),
                            "brand":        m.get("name", ""),
                            "unit":         m.get("unit", ""),
                            "norm_per_unit": norm,
                            "qty_total":    total_q,
                            "variant":      "стандарт",
                            "purchase_price": pp,
                            "client_price": cp,
                        })
                    st.session_state[mat_key] = default_mats
                if chat_key not in st.session_state:
                    st.session_state[chat_key] = []  # история диалога

                # Предварительный подсчёт для заголовка expander
                _mats_preview = st.session_state.get(mat_key, [])
                _mat_preview_total = sum(
                    m.get("client_price", 0) * m.get("qty_total", 0)
                    for m in _mats_preview
                )
                _mat_count = len(_mats_preview)
                _exp_label = (
                    f"📦 Материалы · {_mat_count} поз. · {int(_mat_preview_total):,} ₽"
                    if _mats_preview else "📦 Материалы — нажмите для подбора"
                ).replace(",", " ")
                with st.expander(_exp_label, expanded=False):

                    mat_api = st.secrets.get("ANTHROPIC_API_KEY",
                               os.environ.get("ANTHROPIC_API_KEY", ""))
                    mat_markup = st.number_input(
                        "Наценка на материалы, %", min_value=0, max_value=100,
                        step=5, value=20, key=f"mat_markup_{iid}",
                        help="Скрытая наценка: клиент видит рыночную цену, разница — ваша маржа",
                    )
                    # Кнопка пересчёта объёмов при изменении кол-ва работ
                    if st.button("🔄 Пересчитать объёмы под текущее кол-во",
                                 key=f"mat_recalc_{iid}", use_container_width=True):
                        updated_mats = []
                        for m in st.session_state[mat_key]:
                            norm = m.get("norm_per_unit", 0)
                            if norm > 0:
                                m["qty_total"] = round(norm * float(qty), 2)
                            updated_mats.append(m)
                        st.session_state[mat_key] = updated_mats
                        st.rerun()

                    # Показываем историю диалога
                    for msg in st.session_state[chat_key]:
                        role = msg["role"]
                        if role == "user":
                            st.markdown(f"👤 *{msg['text']}*")
                        else:
                            st.markdown(f"🔧 {msg['text']}")

                    # Показываем текущий список материалов
                    cur_mats = st.session_state[mat_key]
                    if cur_mats:
                        st.markdown("**Выбранные материалы:**")
                        mat_total_client = 0
                        for mi, m in enumerate(cur_mats):
                            qty_m  = m.get("qty_total", 0)
                            cp     = m.get("client_price", 0)
                            pp     = m.get("purchase_price", 0)
                            # Применяем наценку если цена не из каталога
                            if cp == 0 and pp > 0:
                                cp = int(pp * (1 + mat_markup / 100))
                                st.session_state[mat_key][mi]["client_price"] = cp
                            total_m = int(cp * qty_m)
                            mat_total_client += total_m

                            # Строка материала — 2-уровневая компоновка
                            mr1, mr2, mr_del = st.columns([7, 2, 0.6])
                            with mr1:
                                brand_show = m.get('brand') or m.get('name', '—')
                                name_show  = m.get('name', '')
                                if brand_show == name_show:
                                    st.markdown(f"**{brand_show}**")
                                else:
                                    st.markdown(f"**{brand_show}**")
                                    st.caption(name_show)
                            with mr_del:
                                if st.button("✖", key=f"mat_rm_{iid}_{mi}"):
                                    st.session_state[mat_key].pop(mi)
                                    st.rerun()

                            # Вторая строка: количество | вариант | цена за ед | итого
                            mc2, mc3, mc4, mc5 = st.columns([2, 2.5, 2, 2])
                            with mc2:
                                new_qty_m = st.number_input(
                                    m.get("unit", "ед."),
                                    min_value=0.0, value=float(qty_m),
                                    step=0.5, format="%.2f",
                                    key=f"mat_qty_{iid}_{mi}",
                                )
                                if abs(new_qty_m - qty_m) > 0.001:
                                    st.session_state[mat_key][mi]["qty_total"] = new_qty_m
                                    st.rerun()
                            with mc3:
                                v_labels = {"эконом": "💰 Эконом", "стандарт": "✅ Стандарт", "премиум": "⭐ Премиум"}
                                v_opts   = list(v_labels.keys())
                                cur_v    = m.get("variant", "стандарт")
                                v_idx    = v_opts.index(cur_v) if cur_v in v_opts else 1
                                new_v    = st.selectbox("Класс", [v_labels[v] for v in v_opts],
                                                        index=v_idx,
                                                        key=f"mat_var_{iid}_{mi}",
                                                        label_visibility="collapsed")
                                # Конвертируем обратно в ключ
                                new_v_key = {v: k for k, v in v_labels.items()}.get(new_v, new_v)
                                if new_v_key != cur_v:
                                    from materials_agent import MATERIAL_CATALOG
                                    mkey = m.get("key", "")
                                    if mkey in MATERIAL_CATALOG and new_v_key in MATERIAL_CATALOG[mkey]["variants"]:
                                        vdata = MATERIAL_CATALOG[mkey]["variants"][new_v_key]
                                        st.session_state[mat_key][mi].update({
                                            "variant": new_v_key,
                                            "brand": vdata["brand"],
                                            "purchase_price": vdata["purchase"],
                                            "client_price": vdata["client"],
                                        })
                                    else:
                                        st.session_state[mat_key][mi]["variant"] = new_v_key
                                    st.rerun()
                            with mc4:
                                # Если цена не задана — даём ввести
                                if cp == 0:
                                    new_cp = st.number_input(
                                        "Цена ₽/ед.", min_value=0, step=50,
                                        key=f"mat_cp_{iid}_{mi}",
                                        label_visibility="visible",
                                    )
                                    if new_cp > 0:
                                        st.session_state[mat_key][mi]["client_price"] = new_cp
                                        st.session_state[mat_key][mi]["purchase_price"] = int(new_cp / 1.2)
                                        st.rerun()
                                else:
                                    st.metric("₽/ед.", f"{int(cp):,}".replace(",", " "))
                            with mc5:
                                if total_m > 0:
                                    st.metric("Итого", f"{int(total_m):,} ₽".replace(",", " "))
                                else:
                                    st.caption("⚠️ Укажите цену")

                        st.markdown(f"**Итого материалы: {mat_total_client:,} ₽**".replace(",", " "))
                        st.markdown("---")

                    # Поле для ввода пользователя
                    user_mat_input = st.text_input(
                        "Напишите что нужно добавить или изменить",
                        placeholder="ГКЛ Кнауф в 2 слоя, каркас, утеплитель…",
                        key=f"mat_input_{iid}",
                    )
                    col_mat1, col_mat2 = st.columns([3, 1])
                    with col_mat1:
                        if st.button("🔧 Подобрать материалы", key=f"mat_ask_{iid}",
                                     type="primary", use_container_width=True):
                            if user_mat_input.strip() and mat_api:
                                from materials_agent import suggest_materials
                                with st.spinner("Прораб подбирает материалы…"):
                                    result = suggest_materials(
                                        work_name=it["name"],
                                        work_qty=float(qty),
                                        work_unit=it["unit"],
                                        existing_materials=st.session_state[mat_key],
                                        user_message=user_mat_input.strip(),
                                        api_key=mat_api,
                                    )
                                # Добавляем в историю
                                st.session_state[chat_key].append(
                                    {"role": "user", "text": user_mat_input.strip()}
                                )
                                # Добавляем новые материалы (без дублей)
                                existing_names = {m.get("name","") for m in st.session_state[mat_key]}
                                for new_m in result.get("materials", []):
                                    if new_m.get("name") not in existing_names:
                                        # Применяем наценку если нет цены
                                        if new_m.get("client_price", 0) == 0 and new_m.get("purchase_price", 0) > 0:
                                            new_m["client_price"] = int(
                                                new_m["purchase_price"] * (1 + mat_markup / 100)
                                            )
                                        st.session_state[mat_key].append(new_m)
                                        existing_names.add(new_m.get("name",""))
                                # Ответ агента
                                agent_reply = result.get("agent_comment", "")
                                q = result.get("clarifying_question")
                                if q:
                                    agent_reply += f"\n\n❓ **{q}**"
                                if agent_reply:
                                    st.session_state[chat_key].append(
                                        {"role": "agent", "text": agent_reply}
                                    )
                                st.rerun()
                    with col_mat2:
                        if st.button("🗑 Очистить", key=f"mat_clear_{iid}", use_container_width=True):
                            st.session_state[mat_key] = []
                            st.session_state[chat_key] = []
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
                    margin_pct     = st.number_input("Маржа на работы, %", min_value=0, max_value=100, step=5, value=30, key="fin_margin", help="25-35% рекомендуемый диапазон. Применяется к работам.")
                    overhead_pct   = st.number_input("Накладные, %",       min_value=0, max_value=50, step=1, value=5,  key="fin_oh")
                    profit_pct     = st.number_input("Прибыль, %",         min_value=0, max_value=50, step=1, value=0,  key="fin_pr")
                    vat_on         = st.checkbox("НДС 22% (безнал)", value=True, key="fin_vat")

            # Финальный расчёт: маржа на работы, затем накладные+прибыль, затем НДС
            work_with_margin = total_work * (1 + margin_pct / 100)
            base = work_with_margin + total_mat
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
                        # Подмешиваем материалы от агента (клиентские цены, без закупочных)
                        import copy
                        selected_items_ex = []
                        for iid2, e2 in cart.items():
                            item_copy = copy.deepcopy(e2["item"])
                            work_qty2 = e2["qty"]
                            agent_mats = st.session_state.get(f"mat_{iid2}", [])
                            if agent_mats:
                                # Конвертируем в формат справочника: price = client_price
                                converted = []
                                for am in agent_mats:
                                    cp  = am.get("client_price", 0)
                                    qty_m = am.get("qty_total", 0)
                                    norm = round(qty_m / work_qty2, 4) if work_qty2 > 0 else 0
                                    converted.append({
                                        "name":  f"{am.get('brand', am.get('name',''))} ({am.get('name','')})",
                                        "unit":  am.get("unit", "шт."),
                                        "norm":  norm,
                                        "price": cp,
                                    })
                                item_copy["materials"] = converted
                            selected_items_ex.append(item_copy)
                        quantities_ex = {iid: e["qty"] for iid, e in cart.items()}

                        fin_settings["margin_pct"] = int(margin_pct)

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

            # ── Прораб-агент ─────────────────────────────────────────────
            if st.button("🔍 Проверить КП прорабом", use_container_width=True,
                         key="foreman_check", type="secondary"):
                api_key = st.secrets.get("ANTHROPIC_API_KEY",
                           os.environ.get("ANTHROPIC_API_KEY", ""))
                if not api_key:
                    st.warning("Нет ANTHROPIC_API_KEY")
                else:
                    with st.spinner("Прораб изучает КП… (~15 сек)"):
                        from foreman import review_kp
                        try:
                            report = review_kp(
                                cart=cart,
                                obj_name=st.session_state.get("kp_obj", ""),
                                area=st.session_state.get("kp_area", 0),
                                api_key=api_key,
                            )
                            st.session_state["foreman_report"] = report
                        except Exception as e:
                            st.error(f"Ошибка прораба: {e}")

            # ── Отчёт прораба ─────────────────────────────────────────────
            report = st.session_state.get("foreman_report")
            if report:
                verdict = report.get("verdict", "")
                summary = report.get("summary", "")

                # Цвет по вердикту
                if "✅" in verdict:
                    st.success(f"**{verdict}**  \n{summary}")
                elif "❌" in verdict:
                    st.error(f"**{verdict}**  \n{summary}")
                else:
                    st.warning(f"**{verdict}**  \n{summary}")

                # Неясные позиции
                unclear = report.get("unclear_positions", [])
                if unclear:
                    with st.expander(f"❓ Неясные позиции ({len(unclear)}) — уточни у заказчика",
                                     expanded=True):
                        for u in unclear:
                            st.markdown(f"**{u.get('name', '')}**")
                            st.markdown(f"🔸 *Проблема:* {u.get('issue', '')}")
                            st.markdown(f"📋 *Уточнить:* {u.get('clarification_needed', '')}")
                            if u.get("risk"):
                                st.caption(f"⚠️ Риск: {u['risk']}")
                            st.markdown("---")

                # Недостающие позиции
                missing = report.get("missing_items", [])
                if missing:
                    with st.expander(f"🔴 Не хватает позиций ({len(missing)})",
                                     expanded=True):
                        for m in missing:
                            st.markdown(f"**{m.get('missing', '')}**")
                            st.markdown(f"📌 *Причина:* {m.get('reason', '')}")
                            st.caption(
                                f"Вызвано: {m.get('triggered_by', '')}  "
                                f"{'· Норма: ' + m['approx_norm'] if m.get('approx_norm') else ''}"
                            )
                            st.markdown("---")

                # Ценовые риски
                price_risks = report.get("price_risks", [])
                if price_risks:
                    with st.expander(f"💰 Ценовые риски ({len(price_risks)})",
                                     expanded=False):
                        for pr in price_risks:
                            vrdt = pr.get("verdict", "")
                            icon = "✅" if "✅" in vrdt else ("❌" if "❌" in vrdt else "⚠️")
                            st.markdown(
                                f"{icon} **{pr.get('name','')}** — "
                                f"{pr.get('our_price',0):,} ₽/{pr.get('unit','')} × "
                                f"{pr.get('qty',0)} = **{pr.get('total',0):,} ₽**"
                            )
                            st.caption(pr.get("market_comment", ""))

                # Общие замечания прораба
                notes = report.get("foreman_notes", [])
                if notes:
                    with st.expander("📝 Замечания прораба", expanded=False):
                        for note in notes:
                            st.markdown(f"• {note}")

                if st.button("✖ Закрыть отчёт", key="close_report"):
                    st.session_state["foreman_report"] = None
                    st.rerun()

            st.markdown("---")
            if st.button("🗑 Очистить КП", use_container_width=True, key="clear_cart"):
                st.session_state["kp_cart"] = {}
                st.session_state["excel_ready"] = False
                st.session_state["foreman_report"] = None
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
    api_key   = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    gemini_key = st.secrets.get("GEMINI_API_KEY",   os.environ.get("GEMINI_API_KEY", ""))

    if "tz_review"       not in st.session_state: st.session_state["tz_review"]       = None
    if "tz_review_final" not in st.session_state: st.session_state["tz_review_final"] = None

    # ══════════════════════════════════════════
    # ЭТАП 1: Загрузка и AI-разбор — стильный hero
    # ══════════════════════════════════════════
    if st.session_state["tz_review"] is None:

        st.markdown("""
        <div class="upload-hero">
          <h2>Загрузите ТЗ — AI всё разберёт сам</h2>
          <p>Загрузите техническое задание или смету, система автоматически<br>
             извлечёт работы, найдёт их в справочнике и предложит состав КП</p>
          <div class="format-chips">
            <span class="format-chip">📊 Excel</span>
            <span class="format-chip">📄 PDF</span>
            <span class="format-chip">📝 Word</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Перетащите файл сюда или нажмите для выбора",
            type=["xlsx", "xls", "pdf", "docx"],
            key="tz_file",
            label_visibility="collapsed",
        )

        if uploaded:
            # Карточка с инфо о файле
            fsize = round(uploaded.size / 1024, 1)
            st.markdown(f"""
            <div style="background:white;border:1px solid #E2E8F0;border-radius:12px;
                        padding:16px 20px;display:flex;align-items:center;gap:16px;margin:8px 0">
              <div style="font-size:32px">📂</div>
              <div>
                <div style="font-weight:700;font-size:15px;color:#0F172A">{uploaded.name}</div>
                <div style="font-size:13px;color:#64748B;margin-top:2px">{fsize} КБ · Готов к разбору</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            if api_key:
                if st.button("🚀 Запустить AI-разбор", type="primary", use_container_width=True):
                    try:
                        from ai_parser import extract_text, call_claude_api, match_items
                        raw_text = extract_text(uploaded.read(), uploaded.name)
                        if not raw_text.strip():
                            st.error("Не удалось извлечь текст из файла.")
                        else:
                            # ── Пошаговый прогресс ──
                            prog_box = st.empty()
                            def show_step(step, total, emoji, title, detail=""):
                                pct = int(step / total * 100)
                                prog_box.markdown(f"""
<div style="background:white;border:1px solid #E2E8F0;border-radius:14px;padding:20px 24px;margin:8px 0">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:14px">
    <div style="font-size:28px;line-height:1">{emoji}</div>
    <div>
      <div style="font-weight:700;font-size:15px;color:#0F172A">{title}</div>
      <div style="font-size:13px;color:#64748B;margin-top:2px">{detail}</div>
    </div>
    <div style="margin-left:auto;font-size:13px;font-weight:700;color:#1D4ED8">{pct}%</div>
  </div>
  <div style="background:#E2E8F0;border-radius:999px;height:8px;overflow:hidden">
    <div style="background:linear-gradient(90deg,#1D4ED8,#3B82F6);width:{pct}%;height:8px;border-radius:999px"></div>
  </div>
  <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
    {''.join(f'<span style="font-size:11px;padding:3px 10px;border-radius:999px;background:{"#DCFCE7;color:#166534" if i<step else ("#DBEAFE;color:#1E40AF" if i==step else "#F1F5F9;color:#94A3B8")};font-weight:600">{s}</span>' for i,s in enumerate(["Читаю файл","Извлекаю работы","Ищу в справочнике","Готово"]))}
  </div>
</div>""", unsafe_allow_html=True)

                            show_step(1, 4, "📂", "Читаю документ…", f"{uploaded.name}")
                            parsed = call_claude_api(raw_text, api_key)
                            show_step(2, 4, "🤖", "Извлекаю виды работ…", f"Claude Sonnet анализирует текст ТЗ")
                            matched = match_items(parsed, all_items_combined, api_key)
                            show_step(3, 4, "🔍", "Сопоставляю со справочником…", f"Найдено {len(parsed)} позиций")
                            show_step(4, 4, "✅", "Разбор завершён!", f"Проверьте результат ниже")

                            review = []
                            for i, m in enumerate(matched):
                                review.append({
                                    "idx":          i,
                                    "parsed_name":  m["parsed_name"],
                                    "parsed_unit":  m["parsed_unit"],
                                    "qty":          m.get("qty") or 0.0,
                                    "matched_item": m.get("matched_item"),
                                    "matched_id":   m.get("matched_id"),
                                    "confidence":   m.get("confidence", 0.0),
                                    "comment":      m.get("comment", ""),
                                    "in_catalog":   m.get("in_catalog", False),
                                    "include":      True,
                                    "user_comment": "",
                                    "status":       "ai_matched",
                                })

                            not_found = sum(1 for r in review if not r["in_catalog"])
                            found     = len(review) - not_found
                            st.session_state["tz_review"] = review

                            # Стильный итог
                            st.markdown(f"""
                            <div class="stats-bar">
                              <div class="stat-item">
                                <div class="stat-value" style="color:#0F172A">{len(review)}</div>
                                <div class="stat-label">Позиций извлечено</div>
                              </div>
                              <div class="stat-item">
                                <div class="stat-value" style="color:#10B981">{found}</div>
                                <div class="stat-label">Найдено в справочнике</div>
                              </div>
                              <div class="stat-item">
                                <div class="stat-value" style="color:#EF4444">{not_found}</div>
                                <div class="stat-label">Нет в справочнике</div>
                              </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
            else:
                st.warning("⚠️ ANTHROPIC_API_KEY не настроен в Secrets")

    # ══════════════════════════════════════════
    # ЭТАП 2: Проверка человека + применение правок
    # ══════════════════════════════════════════
    else:
        # Определяем какой список показывать: финальный или первичный
        display_list = st.session_state["tz_review_final"] or st.session_state["tz_review"]
        is_final = st.session_state["tz_review_final"] is not None

        # Шапка этапа
        col_hd1, col_hd2, col_hd3 = st.columns([4, 2, 2])
        with col_hd1:
            if is_final:
                st.markdown("### ✅ Состав КП после правок")
                changed_count = sum(1 for r in display_list if r.get("status") in ("modified", "added", "removed"))
                if changed_count:
                    st.caption(f"🟠 Изменено/добавлено/убрано: {changed_count} позиций")
            else:
                st.markdown("### Этап 2 — Проверьте и откорректируйте")
                st.caption("Снимите галочку чтобы исключить · Напишите комментарий чтобы изменить · Допишите по разделу")
        with col_hd2:
            if st.button("🔄 Загрузить новый ТЗ", use_container_width=True):
                st.session_state["tz_review"] = None
                st.session_state["tz_review_final"] = None
                st.rerun()
        with col_hd3:
            if is_final:
                if st.button("✏️ Редактировать дальше", use_container_width=True):
                    # Финальный результат становится новой базой — можно итерировать
                    final_as_base = st.session_state["tz_review_final"]
                    if final_as_base:
                        # Переиндексируем и сбрасываем user_comment для нового раунда
                        for i, row in enumerate(final_as_base):
                            row["idx"] = i
                            row["user_comment"] = ""
                            row["status"] = "ai_matched"
                            row["include"] = row.get("status_prev", row.get("status", "unchanged")) != "removed"
                        st.session_state["tz_review"] = final_as_base
                    st.session_state["tz_review_final"] = None
                    st.rerun()

        st.markdown("---")

        # ── Таблица позиций ─────────────────────────────────────────────
        # Сбор section_comments
        section_comments: dict[str, str] = {}
        seen_sections: list[str] = []

        for row in display_list:
            sec = row["matched_item"]["section"] if row.get("matched_item") else "Не в справочнике"
            if sec not in seen_sections:
                seen_sections.append(sec)

        # Группировка по разделам
        from collections import defaultdict
        by_section: dict[str, list] = defaultdict(list)
        for row in display_list:
            sec = row["matched_item"]["section"] if row.get("matched_item") else "⚠️ Не найдено в справочнике"
            by_section[sec].append(row)

        for sec, rows in by_section.items():
            # Заголовок раздела
            sec_hd, sec_comment_col = st.columns([3, 3])
            with sec_hd:
                n_in_sec = len([r for r in rows if r.get("include", True) and r.get("status") != "removed"])
                st.markdown(
                    f'<div class="sec-header">📁 {sec} &nbsp;<span style="opacity:0.6;font-weight:400">{n_in_sec} поз.</span></div>',
                    unsafe_allow_html=True,
                )
            with sec_comment_col:
                if not is_final:
                    sc = st.text_input(
                        f"Добавить к разделу «{sec}»:",
                        placeholder="Напр: добавить грунтовку и деформационные швы",
                        key=f"sec_comment_{sec}",
                        label_visibility="collapsed",
                    )
                    if sc:
                        section_comments[sec] = sc
                else:
                    st.caption("")

            for row in rows:
                idx    = row["idx"]
                status = row.get("status", "ai_matched")
                conf   = row.get("confidence", 0.0)
                inc    = row.get("include", True)

                # Цвет строки по статусу
                if status == "removed" or not inc:
                    row_color = "🔴"
                elif status == "added":
                    row_color = "🟠"
                elif status == "modified":
                    row_color = "🟠"
                elif conf >= 0.6:
                    row_color = "🟢"
                elif conf >= 0.35:
                    row_color = "🟡"
                else:
                    row_color = "🔴"

                # Оранжевый фон для изменённых (финальный список)
                if is_final and status in ("modified", "added"):
                    st.markdown(
                        f'<div style="background:#FF8C0020;border-left:3px solid #FF8C00;'
                        f'padding:4px 8px;border-radius:4px;margin:2px 0">',
                        unsafe_allow_html=True,
                    )

                rc1, rc2, rc3, rc4, rc5 = st.columns([0.5, 4, 3, 1.5, 2.5])

                with rc1:
                    if not is_final:
                        new_inc = st.checkbox("", value=inc, key=f"tz_inc_{idx}")
                        if new_inc != inc:
                            st.session_state["tz_review"][idx]["include"] = new_inc
                    else:
                        st.markdown("❌" if status == "removed" else ("🟠" if status in ("modified","added") else "✅"))

                with rc2:
                    if status == "added":
                        _pn4 = row.get('parsed_name') or row.get('name') or '—'
                        st.markdown(f"{row_color} **{_pn4}** *(добавлено)*")
                    elif status == "removed":
                        _pn2 = row.get('parsed_name') or row.get('name') or '—'
                        st.markdown(f"~~{_pn2}~~ *(убрано)*")
                    else:
                        _pn3 = row.get('parsed_name') or row.get('name') or '—'
                        st.markdown(f"{row_color} **{_pn3}**")
                    if row.get("matched_item"):
                        st.caption(f"→ {row['matched_item']['name']}")
                    elif not row.get("in_catalog") and not is_final:
                        # Кнопка добавить в справочник
                        if st.button("➕ В справочник", key=f"tz_learn_{idx}"):
                            st.session_state[f"learn_open_{idx}"] = True
                        if st.session_state.get(f"learn_open_{idx}"):
                            lc1, lc2 = st.columns(2)
                            with lc1:
                                lsec = st.selectbox("Раздел", st.session_state["section_order"], key=f"ls_{idx}", label_visibility="collapsed")
                            with lc2:
                                lprice = st.number_input("Цена ₽", min_value=0, step=100, key=f"lp_{idx}", label_visibility="collapsed")
                            if st.button("Сохранить", key=f"lsave_{idx}", type="primary"):
                                from ai_parser import save_to_catalog
                                ni = save_to_catalog(row["parsed_name"], row["parsed_unit"], lprice, lsec, "Из ТЗ")
                                st.session_state["custom_items"].append(ni)
                                st.session_state["tz_review"][idx]["matched_item"] = ni
                                st.session_state["tz_review"][idx]["matched_id"] = ni["id"]
                                st.session_state["tz_review"][idx]["in_catalog"] = True
                                st.session_state[f"learn_open_{idx}"] = False
                                st.rerun()

                with rc3:
                    if not is_final:
                        uc = st.text_input(
                            "Комментарий",
                            value=row.get("user_comment", ""),
                            placeholder="изменить объём / уточнить / убрать…",
                            key=f"tz_uc_{idx}",
                            label_visibility="collapsed",
                        )
                        if uc != row.get("user_comment", ""):
                            st.session_state["tz_review"][idx]["user_comment"] = uc
                    else:
                        if row.get("change_note"):
                            st.caption(f"🟠 {row['change_note']}")

                with rc4:
                    qty_val = float(row.get("qty") or 0)
                    unit_label = (row["matched_item"]["unit"] if row.get("matched_item") else row.get("parsed_unit", "ед."))
                    if not is_final:
                        new_qty = st.number_input(
                            unit_label, min_value=0.0, value=qty_val, step=0.5,
                            format="%.2f", key=f"tz_qty_{idx}", label_visibility="visible",
                        )
                        if abs(new_qty - qty_val) > 0.001:
                            st.session_state["tz_review"][idx]["qty"] = new_qty
                    else:
                        st.markdown(f"**{qty_val:.1f}** {unit_label}")

                with rc5:
                    if is_final and status != "removed":
                        it = row.get("matched_item")
                        if it:
                            iid = it["id"]
                            in_cart = iid in st.session_state["kp_cart"]
                            if in_cart:
                                st.markdown("✅ в КП")
                            else:
                                if st.button("➕ В КП", key=f"tz_final_add_{idx}", use_container_width=True, type="primary"):
                                    cart_add(it, float(row.get("qty") or 0))
                                    st.rerun()
                    elif is_final and gemini_key and not row.get("matched_item"):
                        if st.button("🔍 Цену Gemini", key=f"tz_gem_{idx}", use_container_width=True):
                            from ai_parser import get_market_price
                            pd2 = get_market_price(row["parsed_name"], row["parsed_unit"], gemini_key)
                            st.session_state[f"mp_{idx}"] = pd2
                        if st.session_state.get(f"mp_{idx}"):
                            pd2 = st.session_state[f"mp_{idx}"]
                            st.caption(f"💰 ср. {pd2['price_mid']:,} ₽")

                if is_final and status in ("modified", "added"):
                    st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("")  # отступ между разделами

        st.markdown("---")

        # ── Кнопки действий ─────────────────────────────────────────────
        if not is_final:
            ac1, ac2 = st.columns(2)
            with ac1:
                if st.button("🔄 Применить правки (Claude переработает)", type="primary",
                             use_container_width=True, key="tz_reprocess"):
                    review = st.session_state["tz_review"]
                    has_edits = any(
                        not r.get("include", True) or r.get("user_comment", "").strip()
                        for r in review
                    ) or any(v.strip() for v in section_comments.values())

                    if not has_edits:
                        st.info("Правок нет — состав не изменился.")
                    else:
                        with st.spinner("Claude применяет ваши правки…"):
                            from ai_parser import reprocess_with_edits
                            # Синхронизируем user_comment из виджетов
                            for r in review:
                                r["user_comment"] = st.session_state.get(
                                    f"tz_uc_{r['idx']}", r.get("user_comment", ""))
                                r["include"] = st.session_state.get(
                                    f"tz_inc_{r['idx']}", r.get("include", True))
                                r["qty"] = st.session_state.get(
                                    f"tz_qty_{r['idx']}", r.get("qty", 0))
                            # Собираем section_comments из виджетов
                            sc_final = {}
                            for sec in by_section:
                                sc_val = st.session_state.get(f"sec_comment_{sec}", "")
                                if sc_val:
                                    sc_final[sec] = sc_val
                            final = reprocess_with_edits(review, sc_final, all_items_combined, api_key)
                        st.session_state["tz_review_final"] = final
                        st.rerun()

            with ac2:
                if st.button("✅ Принять как есть → все в КП", use_container_width=True, key="tz_accept_all"):
                    for row in display_list:
                        if row.get("include", True) and row.get("matched_item"):
                            cart_add(row["matched_item"], float(row.get("qty") or 0))
                    st.session_state["tz_review"] = None
                    st.session_state["tz_review_final"] = None
                    st.success("Перенесено в КП! Перейдите на вкладку 📝")
                    st.rerun()

        else:
            # Финальный список: кнопка "Добавить всё в КП"
            if st.button("✅ Добавить весь финальный состав в КП", type="primary",
                         use_container_width=True, key="tz_final_all"):
                for row in display_list:
                    if row.get("status") != "removed" and row.get("matched_item"):
                        cart_add(row["matched_item"], float(row.get("qty") or 0))
                st.session_state["tz_review"] = None
                st.session_state["tz_review_final"] = None
                st.success("Всё перенесено в КП!")
                st.rerun()

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
                    st.caption(f"{m['matched_item']['section']} · {m.get('comment','')}")
                else:
                    st.markdown("⚠️ **Нет в справочнике**")
                    # Кнопка поиска рыночной цены через Gemini
                    gemini_key = st.secrets.get("GEMINI_API_KEY",
                                  os.environ.get("GEMINI_API_KEY", ""))
                    if gemini_key:
                        if st.button("🔍 Найти цену (Gemini)",
                                     key=f"gemini_{idx}", use_container_width=True):
                            from ai_parser import get_market_price
                            with st.spinner("Ищу рыночную цену…"):
                                price_data = get_market_price(
                                    m["parsed_name"], m["parsed_unit"], gemini_key
                                )
                            st.session_state[f"market_price_{idx}"] = price_data
                    if st.session_state.get(f"market_price_{idx}"):
                        pd = st.session_state[f"market_price_{idx}"]
                        st.caption(
                            f"💰 {pd['price_min']:,}–{pd['price_max']:,} ₽ "
                            f"(ср. {pd['price_mid']:,} ₽) · {pd['source']}"
                        )
                    # Кнопка "Добавить в справочник"
                    if st.button("➕ Добавить в справочник", key=f"learn_{idx}",
                                 use_container_width=True):
                        st.session_state[f"learn_open_{idx}"] = True

                    if st.session_state.get(f"learn_open_{idx}"):
                        pd = st.session_state.get(f"market_price_{idx}", {})
                        default_price = pd.get("price_mid", 0)
                        lc1, lc2 = st.columns(2)
                        with lc1:
                            learn_sec = st.selectbox(
                                "Раздел", st.session_state["section_order"],
                                key=f"learn_sec_{idx}", label_visibility="collapsed"
                            )
                        with lc2:
                            learn_price = st.number_input(
                                "Цена ₽/ед.", min_value=0, value=int(default_price),
                                step=100, key=f"learn_price_{idx}",
                                label_visibility="collapsed"
                            )
                        if st.button("✅ Сохранить в справочник",
                                     key=f"learn_save_{idx}", type="primary"):
                            from ai_parser import save_to_catalog
                            new_item = save_to_catalog(
                                name=m["parsed_name"], unit=m["parsed_unit"],
                                price=learn_price, section=learn_sec,
                                subsection="Добавлено из ТЗ",
                            )
                            st.session_state["custom_items"].append(new_item)
                            all_items_combined = all_items + st.session_state["custom_items"]
                            iid = new_item["id"]
                            st.session_state[f"learn_open_{idx}"] = False
                            st.success(f"Сохранено! Теперь будет найдено автоматически.")
                            st.rerun()

                # Возможность заменить матч вручную
                override_names = ["— оставить —"] + [i["name"] for i in all_items_combined[:300]]
                override = st.selectbox("Заменить →", override_names, key=f"tz_ov_{idx}",
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
