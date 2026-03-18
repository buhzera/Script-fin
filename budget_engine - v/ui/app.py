"""
Budget Engine - Painel Principal Streamlit
Fluxo: Gate de sessão → Pasta de inputs → App completo
"""
import streamlit as st
import pandas as pd
import json
import os
import sys
from pathlib import Path
from datetime import date, datetime
from io import BytesIO, StringIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _abrir_pasta_dialog(titulo="Selecionar pasta de inputs") -> str:
    """Abre o explorador de pastas nativo via tkinter. Retorna o path ou ''."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        pasta = filedialog.askdirectory(title=titulo, parent=root)
        root.destroy()
        return pasta or ""
    except Exception:
        return ""

from engine.sinistros import aplicar_sinistros
from engine.comissao_gastos import aplicar_comissao, aplicar_gastos
from engine.resultado import consolidar_resultado
from engine.variaveis_custom import VARIAVEIS_DISPONIVEIS
from engine.persistencia import (
    carregar_persistencia_excel, persistencia_padrao,
    aplicar_persistencia_acumulada, gerar_template_persistencia
)
from engine.savings import carregar_hipoteses_savings, savings_params_dict, aplicar_savings
from engine.session_manager import (
    salvar_sessao, salvar_versao, carregar_sessao, clonar_sessao,
    listar_sessoes_df, listar_versoes, obter_ultima_versao_id, deletar_sessao,
    exportar_sessao_zip, importar_sessao_zip,
    atualizar_pasta_sessao, salvar_resultado_na_versao,
    listar_versoes_com_resultado, carregar_versao,
    salvar_params_na_versao
)
from engine.auditoria import (
    decaimento_certificados, posicao_por_mes, etapas_financeiras,
    filtrar as filtrar_audit,
)

st.set_page_config(
    page_title="Budget Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* ══════════════════════════════════════════════════════
   Budget Engine  Design System
   Green #00965E · Dark #004F30 · Bg #F4F6F5
   ══════════════════════════════════════════════════════ */

/* ── Hide Streamlit chrome ──────────────────────────── */
/* NÃO esconder header inteiro — o botão >> do sidebar fica dentro dele */
#MainMenu, footer { display: none !important; }
[data-testid="stDeployButton"],
[data-testid="stToolbarActions"],
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stStatusWidget"],
[data-testid="stMainMenu"] { display: none !important; }
/* Colapsa o header visualmente sem remover o DOM */
header { height: 0 !important; min-height: 0 !important;
         padding: 0 !important; overflow: visible !important; }
.e1llqode5, .e1llqode6 { display: none !important; }
[data-testid="stException"] a[target="_blank"],
[data-testid="stException"] a[rel~="noopener"],
[data-testid="stExceptionMessage"] a { display: none !important; }

/* ── Global ─────────────────────────────────────────── */
* { box-sizing: border-box; }
.stApp {
    background: #F4F6F5;
    font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
}
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2rem !important;
    max-width: 1300px !important;
}

/* ── Sidebar — dark green ───────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(175deg, #002E18 0%, #003D22 40%, #004F30 100%) !important;
    border-right: none !important;
    box-shadow: 2px 0 12px rgba(0,0,0,0.18) !important;
}
[data-testid="stSidebar"] section { padding-top: 0 !important; }
[data-testid="stSidebar"] * { color: #D4EDE0 !important; }

/* ── Sidebar — sem botão de colapsar, painel sempre fixo ── */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong { color: #FFFFFF !important; }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #B8D9C5 !important; }
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.10) !important;
    margin: 0.75rem 0 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    background: rgba(255,255,255,0.08) !important;
    border-color: rgba(255,255,255,0.15) !important;
    color: #B8D9C5 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 6px !important;
    color: #C8E6D5 !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.10) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.20) !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    transition: all 0.18s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.20) !important;
}

/* ── Tabs ───────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    background: #FFFFFF;
    border-bottom: 1.5px solid #DDE8E3;
    padding: 0 0.5rem;
    border-radius: 10px 10px 0 0;
    box-shadow: 0 1px 0 #DDE8E3;
}
[data-testid="stTabs"] [role="tab"] {
    font-size: 0.80rem !important;
    font-weight: 600 !important;
    color: #777 !important;
    padding: 0.65rem 0.9rem !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    margin-bottom: -1.5px;
    letter-spacing: 0.01em;
    transition: color 0.15s, background 0.15s;
}
[data-testid="stTabs"] [role="tab"]:hover {
    color: #00965E !important;
    background: #F2FAF6 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #004F30 !important;
    border-bottom: 3px solid #00965E !important;
    background: transparent !important;
}
[data-testid="stTabs"] [role="tabpanel"] {
    background: #FFFFFF;
    padding: 1.5rem 1.2rem 2rem !important;
    border-radius: 0 0 10px 10px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.05);
}

/* ── Buttons ────────────────────────────────────────── */
.stButton > button {
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    padding: 0.42rem 1.1rem !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
}
.stButton > button[kind="primary"] {
    background: #00965E !important;
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(0,150,94,0.28) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #007A4C !important;
    box-shadow: 0 4px 14px rgba(0,150,94,0.38) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0) !important; }
.stButton > button[kind="secondary"] {
    background: #FFFFFF !important;
    color: #00965E !important;
    border: 1.5px solid #00965E !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #F0FAF5 !important;
    transform: translateY(-1px) !important;
}

/* ── Headers ────────────────────────────────────────── */
h1 { color: #003D22 !important; font-weight: 700 !important; font-size: 1.55rem !important; letter-spacing: -0.01em !important; }
h2 { color: #004F30 !important; font-weight: 700 !important; font-size: 1.2rem !important; }
h3 { color: #1A1A1A !important; font-weight: 600 !important; font-size: 1rem !important; }

/* ── Metrics — card style ───────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #DDE8E3 !important;
    border-top: 3px solid #00965E !important;
    border-radius: 8px !important;
    padding: 1rem 1.1rem 0.9rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    color: #888 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] > div {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: #004F30 !important;
    letter-spacing: -0.01em !important;
}

/* ── Inputs ─────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
    border-radius: 6px !important;
    border: 1.5px solid #D0DDD8 !important;
    font-size: 0.87rem !important;
    background: #FAFCFB !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #00965E !important;
    box-shadow: 0 0 0 3px rgba(0,150,94,0.12) !important;
    background: #FFFFFF !important;
}
[data-baseweb="select"] > div {
    border-radius: 6px !important;
    border: 1.5px solid #D0DDD8 !important;
    font-size: 0.87rem !important;
    background: #FAFCFB !important;
}
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stCheckbox"] label,
[data-testid="stDateInput"] label {
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    color: #555 !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
}

/* ── Expanders ──────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #DDE8E3 !important;
    border-radius: 8px !important;
    margin-bottom: 0.6rem !important;
    overflow: hidden !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #222 !important;
    padding: 0.8rem 1rem !important;
    background: #F8FAF9 !important;
    transition: background 0.15s;
}
[data-testid="stExpander"] summary:hover {
    background: #EDF5F0 !important;
    color: #00965E !important;
}

/* ── Alerts ─────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 7px !important;
    font-size: 0.85rem !important;
    border-left-width: 4px !important;
}

/* ── Dataframes ─────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    overflow: hidden !important;
    border: 1px solid #DDE8E3 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

/* ── Divider ────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #E5EDEA !important;
    margin: 1.2rem 0 !important;
}

/* ── Captions ───────────────────────────────────────── */
small, .stCaption { color: #999 !important; font-size: 0.77rem !important; }

/* ── Scrollbar ──────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-thumb { background: #00965E; border-radius: 3px; }
::-webkit-scrollbar-track { background: #EDF2EF; }
</style>
""", unsafe_allow_html=True)

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"

# ─────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────

def _carregar_pasta_fonte(pasta_str: str) -> dict:
    """Lê todos os arquivos reconhecidos de uma pasta e popula session_state."""
    pasta = Path(pasta_str)
    if not pasta.exists() or not pasta.is_dir():
        return {"erro": f"Pasta não encontrada: {pasta_str}"}

    carregados, nao_encontrados, erros = [], [], []

    mapa = {
        "stock.csv": "stock",
        "new_business.csv": "nb",
        "sinistros.csv": "sinistros",
        "comissao.csv": "comissao",
        "gastos.csv": "gastos",
        "persistencia.xlsx": "persistencia",
        "savings_hipoteses.csv": "savings_hipoteses",
    }

    for arquivo, tipo in mapa.items():
        caminho = pasta / arquivo
        if not caminho.exists():
            nao_encontrados.append(arquivo)
            continue
        try:
            if tipo == "stock":
                st.session_state["stock_bytes_loaded"] = caminho.read_bytes()
            elif tipo == "nb":
                st.session_state["nb_bytes_loaded"] = caminho.read_bytes()
            elif tipo == "sinistros":
                st.session_state["sin_manual"] = pd.read_csv(caminho, sep=";", decimal=",")
            elif tipo == "comissao":
                st.session_state["com_manual"] = pd.read_csv(caminho, sep=";", decimal=",")
            elif tipo == "gastos":
                st.session_state["gas_manual"] = pd.read_csv(caminho, sep=";", decimal=",")
            elif tipo == "persistencia":
                st.session_state["curvas_persistencia"] = carregar_persistencia_excel(str(caminho))
            elif tipo == "savings_hipoteses":
                st.session_state["savings_hipoteses_manual"] = carregar_hipoteses_savings(str(caminho))
            carregados.append(arquivo)
        except Exception as e:
            erros.append(f"{arquivo}: {e}")

    return {"carregados": carregados, "nao_encontrados": nao_encontrados, "erros": erros}


def _coletar_fallbacks_estado() -> dict:
    """Coleta todos os fallbacks escalares/dict do session_state para persistência na sessão."""
    fb = {}
    for k in [
        "sin_fallback", "sin_fallback_savings",
        "com_fallback", "com_fallback_savings",
        "gas_gastos_fallback", "gas_othernbi_fallback",
        "gas_gastos_fallback_sav", "gas_othernbi_fallback_sav",
        "max_meses_savings",
    ]:
        v = st.session_state.get(k)
        if v is not None:
            fb[k] = v
    return fb


def _restaurar_sessao(dados: dict):
    """Popula session_state a partir de uma sessão carregada."""
    params = dados.get("params") or {}
    if dados.get("stock_bytes"):
        st.session_state["stock_bytes_loaded"] = dados["stock_bytes"]
    if dados.get("nb_bytes"):
        st.session_state["nb_bytes_loaded"] = dados["nb_bytes"]
    if dados.get("df_sinistros") is not None:
        st.session_state["sin_manual"] = dados["df_sinistros"]
    if dados.get("df_comissao") is not None:
        st.session_state["com_manual"] = dados["df_comissao"]
    if dados.get("df_gastos") is not None:
        st.session_state["gas_manual"] = dados["df_gastos"]
    if dados.get("df_premissas_proj") is not None:
        st.session_state["df_premissas_proj"] = dados["df_premissas_proj"]
    if dados.get("nos_custom"):
        st.session_state["nos_custom"] = dados["nos_custom"]
        st.session_state["variaveis_criadas"] = [
            g[-1]["parametros"]["nome_variavel"]
            for g in dados["nos_custom"]
            if g and g[-1]["tipo"] == "saida_variavel"
        ]
    if params.get("horizonte_por_produto"):
        st.session_state["horizonte_por_produto"] = params["horizonte_por_produto"]
    if params.get("max_meses_total"):
        st.session_state["max_meses_total"] = int(params["max_meses_total"])
    if params.get("pasta_fonte"):
        st.session_state["pasta_fonte_sugerida"] = params["pasta_fonte"]

    # Restaura fallbacks de hipóteses — dict E widget keys (para os checkboxes aparecerem pré-setados)
    _fb_salvo = params.get("fallbacks", {})
    # Mapeamento: chave_dict -> [(campo_dict, widget_key), ...]
    _FB_WIDGET_MAP = {
        "sin_fallback":           [("ativo", "sin_fb_ativo"),    ("tipo", "sin_fb_tipo"),
                                   ("valor", "sin_fb_valor"),    ("frequencia", "sin_fb_freq"),
                                   ("severidade_media", "sin_fb_sev")],
        "sin_fallback_savings":   [("ativo", "sin_fb_sav_ativo"), ("tipo", "sin_fb_sav_tipo"),
                                   ("valor", "sin_fb_sav_valor")],
        "com_fallback":           [("ativo", "com_fb_ativo"),    ("tipo", "com_fb_tipo"),
                                   ("valor", "com_fb_valor")],
        "com_fallback_savings":   [("ativo", "com_fb_sav_ativo"), ("tipo", "com_fb_sav_tipo"),
                                   ("valor", "com_fb_sav_valor")],
        "gas_gastos_fallback":    [("ativo", "gas_fb_ativo"),    ("tipo", "gas_fb_tipo"),
                                   ("valor", "gas_fb_valor")],
        "gas_othernbi_fallback":  [("ativo", "nbi_fb_ativo"),    ("tipo", "nbi_fb_tipo"),
                                   ("valor", "nbi_fb_valor")],
        "gas_gastos_fallback_sav":[("ativo", "gas_fb_sav_ativo"), ("tipo", "gas_fb_sav_tipo"),
                                   ("valor", "gas_fb_sav_valor")],
        "gas_othernbi_fallback_sav":[("ativo","nbi_fb_sav_ativo"),("tipo","nbi_fb_sav_tipo"),
                                    ("valor", "nbi_fb_sav_valor")],
    }
    for _k, _campos in _FB_WIDGET_MAP.items():
        if _k in _fb_salvo:
            st.session_state[_k] = _fb_salvo[_k]
            for _campo, _wkey in _campos:
                if _campo in _fb_salvo[_k]:
                    st.session_state[_wkey] = _fb_salvo[_k][_campo]
    if "max_meses_savings" in _fb_salvo:
        st.session_state["max_meses_savings"] = int(_fb_salvo["max_meses_savings"])
    if dados.get("df_fallback_curva") is not None:
        st.session_state["fallback_curva"] = dados["df_fallback_curva"]
    if dados.get("df_fallback_curva_sav") is not None:
        st.session_state["fallback_curva_savings"] = dados["df_fallback_curva_sav"]

    # Sinaliza que Tab 2 deve sincronizar widget keys dos fallbacks no próximo render
    if _fb_salvo:
        st.session_state["_needs_fb_sync"] = True

    st.session_state["sessao_carregada"] = dados["meta"]
    if dados.get("df_resultado") is not None:
        st.session_state["df_resultado"] = dados["df_resultado"]
    if dados.get("df_auditoria") is not None:
        st.session_state["df_auditoria"] = dados["df_auditoria"]


def _get_produtos_carregados() -> set:
    """Retorna conjunto de produto_atuarial presentes no stock e new_business carregados."""
    from io import BytesIO
    produtos = set()
    for key in ["stock_bytes_loaded", "nb_bytes_loaded"]:
        b = st.session_state.get(key)
        if b:
            try:
                df = pd.read_csv(BytesIO(b), sep=";", decimal=",",
                                 usecols=["produto_atuarial"], dtype=str)
                produtos.update(df["produto_atuarial"].dropna().unique())
            except Exception:
                pass
    return produtos


def _painel_sem_hipotese(hip_df, label: str, fallback_ativo: bool,
                         colunas_template: list = None, session_key: str = None,
                         save_key: str = None):
    """
    Mostra aviso sobre produtos sem hipótese cadastrada.
    session_key : prefixo único para as widget keys (evita DuplicateElementKey)
    save_key    : chave do session_state onde a linha nova será salva (padrão = session_key)
    """
    produtos_carregados = _get_produtos_carregados()
    if not produtos_carregados:
        return
    produtos_hip = set()
    if hip_df is not None and "produto_atuarial" in hip_df.columns:
        produtos_hip = {str(p) for p in hip_df["produto_atuarial"].dropna().unique()}
    sem_hip = sorted(produtos_carregados - produtos_hip)
    if sem_hip:
        sufixo = " — **valor padrão (fallback) será aplicado.**" if fallback_ativo \
                 else " — resultado será **0** (ative o fallback para usar um valor padrão)."
        st.warning(
            f"⚠️ **{len(sem_hip)} produto(s) sem hipótese de {label}:** "
            f"`{', '.join(sem_hip)}`{sufixo}"
        )
        if colunas_template and session_key:
            _sk = save_key or session_key  # onde salvar no session_state
            with st.expander(f"➕ Adicionar hipótese para produto(s) sem configuração", expanded=False):
                _prod_sel_add = st.selectbox(
                    "Produto", sem_hip, key=f"_add_hip_prod_{session_key}"
                )
                _bl_add = st.text_input("Business Line", key=f"_add_hip_bl_{session_key}")
                _nova_linha = {"produto_atuarial": _prod_sel_add, "businessline": _bl_add}
                for _col in colunas_template:
                    if _col not in ("produto_atuarial", "businessline"):
                        _nova_linha[_col] = st.text_input(_col, key=f"_add_hip_{session_key}_{_col}")
                if st.button(f"✅ Adicionar à hipótese de {label}", key=f"_add_hip_btn_{session_key}"):
                    _df_base = st.session_state.get(_sk)
                    _df_atual = _df_base if (_df_base is not None and not _df_base.empty) \
                                else pd.DataFrame(columns=list(_nova_linha.keys()))
                    st.session_state[_sk] = pd.concat(
                        [_df_atual, pd.DataFrame([_nova_linha])], ignore_index=True)
                    st.success(f"✅ Produto {_prod_sel_add} adicionado. Salve o CSV para persistir.")
                    st.rerun()
    else:
        st.success(f"✅ Todos os produtos têm hipótese de {label} cadastrada.")


@st.dialog("📊 Comparar Exercícios", width="large")
def _dialog_comparar(df_atual: pd.DataFrame, nome_atual: str,
                     df_comp: pd.DataFrame,  nome_comp: str):
    """Modal de comparação entre dois resultados."""
    import plotly.express as px

    _KPI_PROT = [
        ("Prêmio Emitido",    "valor_premio_emitido"),
        ("Prêmio Ganho",      "premio_ganho_calculado"),
        ("PPNG",              "ppng_calculado"),
        ("Sinistros",         "sinistros_calculado"),
        ("Comissão",          "comissao_calculada"),
        ("Gastos",            "gastos_calculado"),
        ("Other NBI",         "other_nbi_calculado"),
        ("NPBT Local",        "npbt_local"),
        ("NPBT IFRS17",       "npbt_ifrs17"),
        ("Qtd. Certificados", "quantidade_certificados"),
    ]
    _KPI_SAV = [
        ("TAF (Savings)",       "taf_calculado"),
        ("Carregamento (Sav.)", "carregamento_calculado"),
        ("Montante Capital",    "montante_capital"),
        ("Sinistros",           "sinistros_calculado"),
        ("Comissão",            "comissao_calculada"),
        ("Gastos",              "gastos_calculado"),
        ("Other NBI",           "other_nbi_calculado"),
        ("NPBT Local",          "npbt_local"),
        ("Qtd. Certificados",   "quantidade_certificados"),
    ]
    _KPI_TOTAL = [
        ("Prêmio Emitido",      "valor_premio_emitido"),
        ("Prêmio Ganho",        "premio_ganho_calculado"),
        ("TAF (Savings)",       "taf_calculado"),
        ("Carregamento (Sav.)", "carregamento_calculado"),
        ("Montante Capital",    "montante_capital"),
        ("Sinistros",           "sinistros_calculado"),
        ("Comissão",            "comissao_calculada"),
        ("Gastos",              "gastos_calculado"),
        ("Other NBI",           "other_nbi_calculado"),
        ("NPBT Local",          "npbt_local"),
        ("NPBT IFRS17",         "npbt_ifrs17"),
        ("Qtd. Certificados",   "quantidade_certificados"),
    ]

    def _fmt(v):
        if v is None or (isinstance(v, float) and v != v):
            return "—"
        return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _delta_pct(a, b):
        if b and b != 0:
            return (a - b) / abs(b)
        return None

    def _aplicar_filtros(df, fonte_f, prods_f, tipos_f, movs_f):
        d = df.copy()
        if fonte_f and "fonte" in d.columns:
            d = d[d["fonte"].isin(fonte_f)]
        if prods_f and "produto_atuarial" in d.columns:
            d = d[d["produto_atuarial"].astype(str).isin([str(p) for p in prods_f])]
        if tipos_f and "tipo_premio" in d.columns:
            d = d[d["tipo_premio"].isin(tipos_f) | d["tipo_premio"].isna()]
        if movs_f and "movimento" in d.columns:
            d = d[d["movimento"].isin(movs_f) | d["movimento"].isna()]
        return d

    def _render_kpis(da, dc, kpi_cols):
        _cols_kpi = st.columns(3)
        _kpi_idx = 0
        for label, col in kpi_cols:
            v_at = da[col].sum() if col in da.columns else None
            v_cp = dc[col].sum() if col in dc.columns else None
            if (v_at is None or v_at == 0) and (v_cp is None or v_cp == 0):
                continue
            delta = _delta_pct(v_at or 0, v_cp or 0)
            with _cols_kpi[_kpi_idx % 3]:
                st.markdown(f"**{label}**")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"<div style='font-size:0.75rem;color:rgba(255,255,255,0.45)'>{nome_atual[:18]}</div>"
                                f"<div style='font-size:0.95rem;font-weight:600'>{_fmt(v_at)}</div>",
                                unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div style='font-size:0.75rem;color:rgba(255,255,255,0.45)'>{nome_comp[:18]}</div>"
                                f"<div style='font-size:0.95rem;font-weight:600'>{_fmt(v_cp)}</div>",
                                unsafe_allow_html=True)
                if delta is not None:
                    cor = "#2ECC71" if delta >= 0 else "#E74C3C"
                    sinal = "+" if delta >= 0 else ""
                    st.markdown(f"<div style='font-size:0.8rem;color:{cor};font-weight:600'>"
                                f"{sinal}{delta:.1%}</div>", unsafe_allow_html=True)
                st.markdown("")
            _kpi_idx += 1

    def _render_pl(da, dc, kpi_cols, na_short, nc_short):
        _pl_rows = []
        for label, col in kpi_cols:
            v_at = da[col].sum() if col in da.columns else 0
            v_cp = dc[col].sum() if col in dc.columns else 0
            if v_at == 0 and v_cp == 0:
                continue
            delta_abs = v_at - v_cp
            delta_pct = _delta_pct(v_at, v_cp)
            _pl_rows.append({
                "Indicador":  label,
                na_short:     _fmt(v_at),
                nc_short:     _fmt(v_cp),
                "Δ Absoluto": _fmt(delta_abs),
                "Δ %":        f"{'+' if (delta_pct or 0) >= 0 else ''}{delta_pct:.1%}" if delta_pct is not None else "—",
            })
        if _pl_rows:
            st.dataframe(pd.DataFrame(_pl_rows), width="stretch", hide_index=True)
        return _pl_rows

    def _render_grafico(da, dc, kpi_cols, na_short, nc_short, tab_key):
        if "mes_projecao" not in da.columns and "mes_projecao" not in dc.columns:
            return
        _vars_graf = {label: col for label, col in kpi_cols
                      if (col in da.columns and da[col].sum() != 0) or
                         (col in dc.columns and dc[col].sum() != 0)}
        if not _vars_graf:
            return
        _default_var = "NPBT Local" if "NPBT Local" in _vars_graf else list(_vars_graf.keys())[0]
        _var_sel = st.selectbox("Variável", list(_vars_graf.keys()),
                                index=list(_vars_graf.keys()).index(_default_var),
                                key=f"cmp_var_graf_{tab_key}")
        _col_sel = _vars_graf[_var_sel]
        _frames_graf = []
        for _df_g, _nome_g in [(da, nome_atual), (dc, nome_comp)]:
            if "mes_projecao" in _df_g.columns and _col_sel in _df_g.columns:
                _tmp = _df_g.groupby("mes_projecao")[_col_sel].sum().reset_index()
                _tmp["Exercício"] = _nome_g[:35]
                _frames_graf.append(_tmp)
        if _frames_graf:
            _df_graf = pd.concat(_frames_graf, ignore_index=True).sort_values("mes_projecao")
            _fig_cmp = px.line(
                _df_graf, x="mes_projecao", y=_col_sel, color="Exercício",
                markers=True,
                title=f"{_var_sel} — {na_short} vs {nc_short}",
                labels={"mes_projecao": "Mês", _col_sel: _var_sel},
            )
            st.plotly_chart(_fig_cmp, width="stretch")

    # ── Filtros ───────────────────────────────────────────
    st.markdown(f"**{nome_atual}** vs **{nome_comp}**")
    with st.expander("🔎 Filtros", expanded=False):
        _fc1, _fc2, _fc3, _fc4 = st.columns(4)
        _todas_fontes = sorted(set(
            list(df_atual["fonte"].dropna().unique() if "fonte" in df_atual.columns else []) +
            list(df_comp["fonte"].dropna().unique()  if "fonte" in df_comp.columns  else [])
        ))
        _todos_prods = sorted(set(
            list(df_atual["produto_atuarial"].dropna().astype(str).unique() if "produto_atuarial" in df_atual.columns else []) +
            list(df_comp["produto_atuarial"].dropna().astype(str).unique()  if "produto_atuarial" in df_comp.columns  else [])
        ))
        _todos_tipos = sorted(set(
            list(df_atual["tipo_premio"].dropna().unique() if "tipo_premio" in df_atual.columns else []) +
            list(df_comp["tipo_premio"].dropna().unique()  if "tipo_premio" in df_comp.columns  else [])
        ))
        _todos_movs = sorted(set(
            list(df_atual["movimento"].dropna().unique() if "movimento" in df_atual.columns else []) +
            list(df_comp["movimento"].dropna().unique()  if "movimento" in df_comp.columns  else [])
        ))
        with _fc1:
            _f_fonte = st.multiselect("Fonte", _todas_fontes, default=_todas_fontes, key="cmp_fonte")
        with _fc2:
            _f_prod = st.multiselect("Produto", _todos_prods, default=_todos_prods, key="cmp_prod")
        with _fc3:
            _f_tipo = st.multiselect("Tipo Prêmio", _todos_tipos, default=_todos_tipos, key="cmp_tipo")
        with _fc4:
            _f_mov = st.multiselect("Movimento", _todos_movs, default=_todos_movs, key="cmp_mov")

    _da = _aplicar_filtros(df_atual, _f_fonte, _f_prod, _f_tipo, _f_mov)
    _dc = _aplicar_filtros(df_comp,  _f_fonte, _f_prod, _f_tipo, _f_mov)

    _na_short = nome_atual[:18]
    _nc_short = nome_comp[:18]

    # Detecta se há múltiplas categorias
    _cats_da = set(_da["categoria"].dropna().unique()) if "categoria" in _da.columns else set()
    _cats_dc = set(_dc["categoria"].dropna().unique()) if "categoria" in _dc.columns else set()
    _cats_all = sorted(_cats_da | _cats_dc)
    _tem_multi_cat = len(_cats_all) > 1

    st.markdown("---")

    if _tem_multi_cat:
        _tab_labels = ["📊 Total"] + [f"🏥 {c}" if c == "Protection" else f"💰 {c}" for c in _cats_all]
        _tabs = st.tabs(_tab_labels)
    else:
        _tabs = [st.container()]
        _tab_labels = ["📊 Total"]

    for _ti, (_tab, _tab_label) in enumerate(zip(_tabs, _tab_labels)):
        with _tab:
            if _ti == 0:  # Total
                _da_v = _da
                _dc_v = _dc
                _kpi_cols_v = _KPI_TOTAL
            else:
                _cat = _cats_all[_ti - 1]
                _da_v = _da[_da["categoria"] == _cat] if "categoria" in _da.columns else _da
                _dc_v = _dc[_dc["categoria"] == _cat] if "categoria" in _dc.columns else _dc
                _kpi_cols_v = _KPI_SAV if _cat == "Savings" else _KPI_PROT

            _render_kpis(_da_v, _dc_v, _kpi_cols_v)
            st.markdown("---")
            st.markdown(f"#### P&L Comparativo — {_tab_label}")
            _pl_rows_last = _render_pl(_da_v, _dc_v, _kpi_cols_v, _na_short, _nc_short)
            st.markdown("---")
            st.markdown("#### Evolução por Mês")
            _render_grafico(_da_v, _dc_v, _kpi_cols_v, _na_short, _nc_short, str(_ti))

    # ── Exportar PDF ─────────────────────────────────────
    st.markdown("---")
    if st.button("⬇️ Exportar como PDF", key="cmp_pdf"):
        try:
            from datetime import datetime as _dt

            def _html_row(row, bold=False):
                tag = "th" if bold else "td"
                cells = "".join(f"<{tag} style='padding:5px 10px;border:1px solid #ddd;text-align:right'>"
                                f"{v}</{tag}>" for v in row)
                return f"<tr>{cells}</tr>"

            # Build total P&L for PDF
            _pdf_rows = []
            for label, col in _KPI_TOTAL:
                v_at = _da[col].sum() if col in _da.columns else 0
                v_cp = _dc[col].sum() if col in _dc.columns else 0
                if v_at == 0 and v_cp == 0:
                    continue
                delta_abs = v_at - v_cp
                delta_pct = _delta_pct(v_at, v_cp)
                _pdf_rows.append({
                    "Indicador": label,
                    _na_short:   _fmt(v_at),
                    _nc_short:   _fmt(v_cp),
                    "Δ Absoluto": _fmt(delta_abs),
                    "Δ %": f"{'+' if (delta_pct or 0) >= 0 else ''}{delta_pct:.1%}" if delta_pct is not None else "—",
                })
            _df_pl_pdf = pd.DataFrame(_pdf_rows) if _pdf_rows else pd.DataFrame()

            _header = list(_df_pl_pdf.columns) if not _df_pl_pdf.empty else []
            _rows_html = _html_row(_header, bold=True)
            for _, r in _df_pl_pdf.iterrows():
                _rows_html += _html_row(r.tolist())

            _html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
            <style>body{{font-family:Arial,sans-serif;padding:20px;font-size:12px}}
            h2{{color:#003D22}}table{{border-collapse:collapse;width:100%}}
            th{{background:#003D22;color:#fff}}</style></head><body>
            <h2>Comparação de Exercícios</h2>
            <p><b>Atual:</b> {nome_atual} &nbsp;|&nbsp; <b>Comparado:</b> {nome_comp}</p>
            <p>Gerado em: {_dt.now().strftime('%d/%m/%Y %H:%M')}</p>
            <table>{_rows_html}</table></body></html>"""

            st.download_button(
                "📄 Baixar HTML (abra no navegador e imprima como PDF)",
                data=_html.encode("utf-8"),
                file_name=f"comparacao_{_dt.now().strftime('%Y%m%d_%H%M')}.html",
                mime="text/html",
                key="cmp_pdf_download",
            )
            st.caption("Dica: abra o arquivo no navegador e use Ctrl+P → Salvar como PDF.")
        except Exception as _e:
            st.error(f"Erro ao gerar: {_e}")


def _aviso_sem_pasta():
    """Exibe aviso se pasta de inputs não estiver configurada."""
    if not st.session_state.get("pasta_fonte", ""):
        st.warning("⚠️ Nenhuma pasta de inputs configurada — as alterações não serão salvas nos arquivos. "
                   "Configure a pasta na tela inicial da sessão.")


def _auto_salvar_csv(df: pd.DataFrame, nome_arquivo: str, chave_hash: str):
    """Salva df no arquivo CSV da pasta de inputs se houve alteração."""
    pasta = st.session_state.get("pasta_fonte", "")
    if not pasta or df is None or df.empty:
        return
    try:
        hash_atual = int(pd.util.hash_pandas_object(df, index=False).sum())
    except Exception:
        hash_atual = hash(df.to_csv())
    if st.session_state.get(chave_hash) == hash_atual:
        return
    try:
        Path(pasta, nome_arquivo).write_text(
            df.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"),
            encoding="utf-8-sig",
        )
        st.session_state[chave_hash] = hash_atual
    except Exception as e:
        st.toast(f"⚠️ Não foi possível salvar {nome_arquivo}: {e}", icon="⚠️")


def _build_horizonte_df() -> pd.DataFrame:
    """Constrói DataFrame do horizonte unindo dados de stock e NBI."""
    # Se já existe premissas salvas, usa elas
    if "df_premissas_proj" in st.session_state:
        df = st.session_state["df_premissas_proj"].copy()
        for col in ["produto_atuarial", "businessline"]:
            if col in df.columns:
                df[col] = df[col].astype(str)
        if "meses" in df.columns:
            df["meses"] = df["meses"].astype(int)
        return df

    rows = []
    for tipo_dado, key in [("Stock", "stock_bytes_loaded"), ("New Business", "nb_bytes_loaded")]:
        if key not in st.session_state:
            continue
        try:
            df = pd.read_csv(BytesIO(st.session_state[key]), sep=";", decimal=",")
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            cols_chave = [c for c in ["produto_atuarial", "businessline"] if c in df.columns]
            if not cols_chave:
                continue
            combos = df[cols_chave + (["categoria"] if "categoria" in df.columns else [])].drop_duplicates().copy()
            combos["tipo"] = tipo_dado
            if "categoria" not in combos.columns:
                combos["categoria"] = "Protection"
            # Savings não usa duração (fundo sem prazo)
            combos["meses"] = combos["categoria"].apply(lambda c: 0 if c == "Savings" else 12)
            rows.append(combos)
        except Exception:
            pass

    if rows:
        df_all = pd.concat(rows, ignore_index=True)
        for col in ["produto_atuarial", "businessline"]:
            if col not in df_all.columns:
                df_all[col] = ""
            else:
                df_all[col] = df_all[col].astype(str)
        if "categoria" not in df_all.columns:
            df_all["categoria"] = "Protection"
        df_all["meses"] = df_all["meses"].astype(int)
        return df_all[["categoria", "produto_atuarial", "businessline", "tipo", "meses"]]

    return pd.DataFrame({
        "categoria": pd.Series(dtype="str"),
        "produto_atuarial": pd.Series(dtype="object"),
        "businessline": pd.Series(dtype="str"),
        "tipo": pd.Series(dtype="str"),
        "meses": pd.Series(dtype="int"),
    })


def _salvar_premissas(df: pd.DataFrame, session_id: str):
    """Salva premissas_proj.csv na pasta da sessão."""
    path = SESSIONS_DIR / f"premissas_proj_{session_id}.csv"
    df.to_csv(path, sep=";", decimal=",", index=False, encoding="utf-8-sig")


def _horizonte_dict(df: pd.DataFrame) -> dict:
    """Converte tabela de premissas para dict {produto: meses} usado pelo engine.
    Savings é excluído — não usa horizonte de renovação."""
    h = {"default": 12}
    for _, row in df.iterrows():
        cat = str(row.get("categoria", "Protection")).strip()
        if cat == "Savings":
            continue
        prod = str(row.get("produto_atuarial", "")).strip()
        meses = int(row.get("meses", 12))
        if prod:
            h[prod] = meses
    return h


# ─────────────────────────────────────────────────────
# Session State Init
# ─────────────────────────────────────────────────────
for _k, _v in [
    ("df_resultado", None),
    ("df_auditoria", None),
    ("df_projecao", None),  # Bloco 1: pós-expansão, pós-persistência, pré-hipóteses
    ("nos_custom", []),
    ("variaveis_criadas", []),
    ("gate_step", 0),  # 0=escolha sessão  1=pasta fonte  2=app
    ("sessao_carregada", None),
    ("pasta_fonte", ""),
    ("sin_fallback",              {"ativo": False, "tipo": "percentual_premio_ganho", "valor": 0.40, "frequencia": 0.0, "severidade_media": 0.0}),
    ("sin_fallback_savings",      {"ativo": False, "tipo": "valor_fixo", "valor": 5.0, "frequencia": 0.0, "severidade_media": 0.0}),
    ("com_fallback",              {"ativo": False, "tipo": "percentual_premio_emitido", "valor": 0.15}),
    ("com_fallback_savings",      {"ativo": False, "tipo": "valor_fixo", "valor": 2.0}),
    ("gas_gastos_fallback",       {"ativo": False, "tipo": "percentual_premio_ganho", "valor": 0.10}),
    ("gas_othernbi_fallback",     {"ativo": False, "tipo": "percentual_premio_ganho", "valor": 0.05}),
    ("gas_gastos_fallback_sav",   {"ativo": False, "tipo": "valor_fixo", "valor": 1.0}),
    ("gas_othernbi_fallback_sav", {"ativo": False, "tipo": "valor_fixo", "valor": 0.5}),
    ("curvas_persistencia_savings", {}),
    ("fallback_curva_savings", None),
    ("max_meses_savings", 120),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ═══════════════════════════════════════════════════════
# GATE — bloqueia o app até sessão + pasta estarem ativos
# ═══════════════════════════════════════════════════════
if st.session_state["gate_step"] < 2:

    # ── Gate-specific CSS ────────────────────────────────
    st.markdown("""
    <style>
    /* Gate: full-width content */
    .block-container { max-width: 1100px !important; padding-top: 0.8rem !important; }

    /* Gate hero banner */
    .gate-hero {
        background: linear-gradient(135deg, #001D10 0%, #003D22 45%, #005C35 80%, #00784A 100%);
        border-radius: 16px;
        padding: 2rem 2.8rem;
        margin-bottom: 1.6rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 8px 36px rgba(0,47,24,0.28);
    }
    .gate-hero-left { display: flex; flex-direction: column; gap: 0.2rem; }
    .gate-hero-eyebrow {
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.20em;
        text-transform: uppercase; color: rgba(255,255,255,0.45);
    }
    .gate-hero-title {
        font-size: 2.1rem; font-weight: 800; color: #FFFFFF;
        line-height: 1.1; letter-spacing: -0.025em;
    }
    .gate-hero-sub {
        font-size: 0.9rem; color: rgba(255,255,255,0.55); margin-top: 0.15rem;
    }
    .gate-hero-right {
        display: flex; flex-direction: column; align-items: flex-end; gap: 0.4rem;
    }
    .gate-hero-badge {
        background: rgba(255,255,255,0.10);
        border: 1px solid rgba(255,255,255,0.20);
        border-radius: 99px; padding: 0.3rem 1rem;
        font-size: 0.70rem; font-weight: 600; color: rgba(255,255,255,0.65);
        letter-spacing: 0.05em;
    }
    .gate-hero-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: #7DDBB0; box-shadow: 0 0 8px #7DDBB0;
        display: inline-block; margin-right: 6px;
    }
    .gate-hero-status { font-size: 0.72rem; color: rgba(255,255,255,0.50); }

    /* Gate form header */
    .gate-form-header { margin-bottom: 1.2rem; }
    .gate-form-eyebrow {
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.16em;
        text-transform: uppercase; color: #00965E; margin-bottom: 0.25rem;
    }
    .gate-form-title {
        font-size: 1.5rem; font-weight: 700; color: #002E18; line-height: 1.2;
    }

    /* Step 1 session pill */
    .gate-session-pill {
        display: inline-flex; align-items: center; gap: 0.5rem;
        background: #EBF7F2; border: 1.5px solid #00965E;
        border-radius: 99px; padding: 0.4rem 1rem;
        font-size: 0.85rem; font-weight: 600; color: #004F30;
        margin-bottom: 1.4rem;
    }
    .gate-session-pill-dot {
        width: 7px; height: 7px; border-radius: 50%; background: #00965E;
    }

    /* Step 1 folder display */
    .gate-folder-box {
        background: #F4F6F5; border: 1.5px solid #C8DDD5;
        border-radius: 10px; padding: 0.9rem 1.1rem;
        font-size: 0.82rem; color: #003D22; font-family: monospace;
        word-break: break-all; margin: 0.8rem 0 1.2rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero banner ──────────────────────────────────────
    st.markdown("""
    <div class="gate-hero">
        <div class="gate-hero-left">
            <div class="gate-hero-eyebrow">Budget Engine</div>
            <div class="gate-hero-title">Budget Engine</div>
            <div class="gate-hero-sub">Plataforma de projeção e análise financeira · Atuária &amp; Finanças</div>
        </div>
        <div class="gate-hero-right">
            <div class="gate-hero-badge">Versão 1.0 · 2026</div>
            <div class="gate-hero-status">
                <span class="gate-hero-dot"></span>Sistema operacional
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── STEP 0: Escolha de sessão ─────────────────────
    if st.session_state["gate_step"] == 0:

        col_center = st.columns([1, 2, 1])[1]
        with col_center:
            st.markdown("""
            <div class="gate-form-header">
                <div class="gate-form-eyebrow">Início de sessão</div>
                <div class="gate-form-title">Selecione ou crie uma sessão</div>
            </div>
            """, unsafe_allow_html=True)

            tab_nova, tab_carregar, tab_importar = st.tabs([
                "✨ Nova Sessão", "📂 Carregar / Clonar", "📥 Importar ZIP"
            ])

            with tab_nova:
                st.markdown("##### Criar nova sessão de trabalho")
                nome_nova = st.text_input("Nome da sessão *", placeholder="ex: Budget 2026 Base")
                autor_nova = st.text_input("Autor", placeholder="ex: João Silva")
                desc_nova = st.text_area("Descrição", placeholder="ex: Cenário base Janeiro/2026", height=80)

                if st.button("✨ Criar e Continuar", type="primary", width="stretch"):
                    if not nome_nova.strip():
                        st.warning("Digite um nome para a sessão.")
                    else:
                        sid = salvar_sessao(
                            nome=nome_nova.strip(),
                            descricao=desc_nova,
                            autor=autor_nova,
                            mes_base=str(date.today().replace(day=1)),
                            visao="LOCAL",
                            usar_paa=True,
                            taxa_desconto=0.0,
                            percentual_ra=0.05,
                            horizonte_por_produto={"default": 12},
                        )
                        st.session_state["sessao_carregada"] = {
                            "id": sid,
                            "sessao_raiz_id": sid,
                            "nome_sessao": nome_nova.strip(),
                            "nome_versao": "V1",
                            "versao_num": 1,
                            "nome": nome_nova.strip(),
                            "autor": autor_nova,
                            "descricao": desc_nova,
                            "criado_em": datetime.now().isoformat()
                        }
                        st.session_state["gate_step"] = 1
                        st.rerun()

            with tab_carregar:
                sessoes = listar_sessoes_df()
                if sessoes.empty:
                    st.info("Nenhuma sessão salva. Crie uma nova na aba ao lado.")
                else:
                    opcoes = {
                        f"{r['nome_sessao']} — {r['criado_em'][:16]}": r["sessao_raiz_id"]
                        for _, r in sessoes.iterrows()
                    }
                    sel_label = st.selectbox("Sessão", list(opcoes.keys()),
                                             key="gate_sel_sessao")
                    sel_id = opcoes[sel_label]

                    col_map = {
                        "nome_sessao": "Sessão", "autor": "Autor",
                        "criado_em": "Criado em", "n_versoes": "Versões",
                        "ultima_versao": "Última Versão",
                    }
                    df_show = sessoes.rename(columns=col_map)
                    cols_show = [c for c in col_map.values() if c in df_show.columns]
                    st.dataframe(df_show[cols_show], width="stretch", height=150)

                    if st.button("▶ Carregar e Trabalhar", type="primary",
                                 width="stretch", key="gate_btn_carregar"):
                        with st.spinner("Carregando sessão..."):
                            vid = obter_ultima_versao_id(sel_id) or sel_id
                            dados = carregar_sessao(vid)
                            _restaurar_sessao(dados)
                        st.session_state["gate_step"] = 1
                        st.rerun()

                    col_e1, col_e2, col_e3 = st.columns(3)
                    with col_e1:
                        if st.button("🔁 Clonar", width="stretch",
                                     key="gate_btn_clonar"):
                            st.session_state["_gate_clonar_aberto"] = True
                            st.rerun()
                    with col_e2:
                        if st.button("⬇ Exportar ZIP", width="stretch",
                                     key="gate_btn_zip"):
                            zb = exportar_sessao_zip(sel_id)
                            st.download_button("📦 Download", zb, f"{sel_id}.zip",
                                               "application/zip", width="stretch",
                                               key="gate_dl_zip")
                    with col_e3:
                        if st.button("🗑 Deletar", width="stretch",
                                     type="secondary", key="gate_btn_deletar"):
                            deletar_sessao(sel_id)
                            st.warning("Sessão deletada.")
                            st.rerun()

                    if st.session_state.get("_gate_clonar_aberto"):
                        st.markdown("---")
                        nome_clone = st.text_input("Nome do clone",
                                                    placeholder="ex: Budget 202602",
                                                    key="gate_nome_clone")
                        col_cc1, col_cc2 = st.columns(2)
                        with col_cc1:
                            if st.button("✅ Confirmar Clone e Abrir", type="primary",
                                         width="stretch", key="gate_btn_conf_clone"):
                                if nome_clone.strip():
                                    with st.spinner("Clonando..."):
                                        novo_id = clonar_sessao(sel_id, nome_clone.strip())
                                        dados = carregar_sessao(novo_id)
                                        _restaurar_sessao(dados)
                                    st.session_state.pop("_gate_clonar_aberto", None)
                                    st.session_state["gate_step"] = 1
                                    st.rerun()
                                else:
                                    st.warning("Digite o nome do clone.")
                        with col_cc2:
                            if st.button("↩ Cancelar", width="stretch",
                                         key="gate_btn_cancel_clone"):
                                st.session_state.pop("_gate_clonar_aberto", None)
                                st.rerun()

            with tab_importar:
                st.markdown("##### Importar sessão de outro ambiente")
                zip_import = st.file_uploader("Arquivo .zip exportado", type=["zip"])
                nome_import = st.text_input("Nome para a sessão importada",
                                             placeholder="ex: Budget 202601 (recebido)")
                if zip_import and st.button("📥 Importar e Abrir", type="primary",
                                             width="stretch"):
                    novo_id = importar_sessao_zip(zip_import.read(), nome_import or None)
                    dados = carregar_sessao(novo_id)
                    _restaurar_sessao(dados)
                    st.session_state["gate_step"] = 1
                    st.rerun()

    # ── STEP 1: Pasta de inputs ───────────────────────
    elif st.session_state["gate_step"] == 1:
        meta_c = st.session_state.get("sessao_carregada", {})
        _nome_s = meta_c.get("nome_sessao") or meta_c.get("nome", "—")
        _nome_v = meta_c.get("nome_versao") or ""

        col_center = st.columns([1, 2, 1])[1]
        with col_center:
            # Session pill
            _pill_label = _nome_s + (f" · {_nome_v}" if _nome_v else "")
            st.markdown(f"""
            <div class="gate-session-pill">
                <div class="gate-session-pill-dot"></div>
                {_pill_label}
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div class="gate-form-header">
                <div class="gate-form-eyebrow">Passo 2 de 2</div>
                <div class="gate-form-title">Pasta de inputs</div>
            </div>
            """, unsafe_allow_html=True)

            pasta_sug = st.session_state.get("pasta_fonte_sugerida", "")
            alterando = st.session_state.get("_trocar_pasta_gate", False)

            def _confirmar_pasta(pasta: str):
                """Carrega a pasta, salva na sessão e avança."""
                with st.spinner("Carregando arquivos..."):
                    res = _carregar_pasta_fonte(pasta)
                if "erro" in res:
                    st.error(res["erro"])
                    return
                st.session_state["pasta_fonte"] = pasta
                st.session_state.pop("_pasta_gate_tmp", None)
                st.session_state.pop("_trocar_pasta_gate", None)
                sid = (st.session_state.get("sessao_carregada") or {}).get("id")
                if sid:
                    atualizar_pasta_sessao(sid, pasta)
                st.session_state["gate_step"] = 2
                st.rerun()

            if pasta_sug and not alterando:
                st.markdown("Pasta de inputs configurada para esta sessão:")
                st.markdown(f'<div class="gate-folder-box">📁 {pasta_sug}</div>',
                            unsafe_allow_html=True)

                if st.button("▶ Continuar com esta pasta", type="primary",
                             width="stretch"):
                    _confirmar_pasta(pasta_sug)

                st.markdown(" ")
                if st.button("Alterar fonte de inputs", width="stretch"):
                    st.session_state["_trocar_pasta_gate"] = True
                    st.rerun()

            else:
                if alterando:
                    st.caption(f"Fonte atual: `{pasta_sug}`")

                pasta_tmp = st.session_state.get("_pasta_gate_tmp", "")
                if pasta_tmp:
                    st.markdown("Pasta selecionada:")
                    st.markdown(f'<div class="gate-folder-box">📁 {pasta_tmp}</div>',
                                unsafe_allow_html=True)

                col_b1, col_b2 = st.columns([3, 1])
                with col_b1:
                    lbl = "📂 Selecionar pasta de inputs" if not pasta_tmp else "📂 Escolher outra pasta"
                    if st.button(lbl, type="primary", width="stretch"):
                        escolhida = _abrir_pasta_dialog()
                        if escolhida:
                            st.session_state["_pasta_gate_tmp"] = escolhida
                            st.rerun()
                        else:
                            st.warning("Nenhuma pasta selecionada.")
                with col_b2:
                    if alterando:
                        if st.button("↩ Cancelar", width="stretch"):
                            st.session_state.pop("_trocar_pasta_gate", None)
                            st.session_state.pop("_pasta_gate_tmp", None)
                            st.rerun()
                    else:
                        if st.button("Pular", width="stretch"):
                            st.session_state["gate_step"] = 2
                            st.rerun()

                if pasta_tmp:
                    if st.button("✅ Confirmar e Entrar", type="primary",
                                 width="stretch"):
                        _confirmar_pasta(pasta_tmp)

    st.stop()


# ═══════════════════════════════════════════════════════
# APP PRINCIPAL (gate_step == 2)
# ═══════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────
with st.sidebar:
    # ── Branding ───────────────────────────────────────
    st.markdown("""
    <div style="padding:1.2rem 0.5rem 1rem;border-bottom:1px solid rgba(255,255,255,0.10);margin-bottom:0.5rem;">
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.18em;
                    color:rgba(255,255,255,0.45);text-transform:uppercase;margin-bottom:3px;">
            Budget Engine
        </div>
        <div style="font-size:1.25rem;font-weight:700;color:#FFFFFF;line-height:1.1;letter-spacing:-0.01em;">
            Budget Engine
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sessão ativa ───────────────────────────────────
    meta_c = st.session_state.get("sessao_carregada", {})
    if meta_c:
        nome_s = meta_c.get("nome_sessao") or meta_c.get("nome", "—")
        nome_v = meta_c.get("nome_versao") or ""
        autor_c = meta_c.get("autor", "—")
        criado_c = str(meta_c.get("criado_em", ""))[:16]
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.14);
                    border-radius:8px;padding:0.8rem 0.9rem;margin:0.3rem 0 0.8rem;">
            <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.1em;
                        color:rgba(255,255,255,0.45);text-transform:uppercase;margin-bottom:4px;">
                Sessão Ativa
            </div>
            <div style="font-size:0.95rem;font-weight:700;color:#FFFFFF;margin-bottom:2px;">
                {nome_s}
            </div>
            {"" if not nome_v else f'<div style="font-size:0.78rem;color:#9ECFB5;margin-bottom:4px;">{nome_v}</div>'}
            <div style="font-size:0.72rem;color:rgba(255,255,255,0.38);">
                {autor_c} · {criado_c}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Pasta de Inputs ────────────────────────────────
    st.markdown('<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;color:rgba(255,255,255,0.4);text-transform:uppercase;margin:0.3rem 0 0.4rem;">Inputs</div>', unsafe_allow_html=True)
    with st.expander("📁 Pasta de Inputs"):
        pasta_atual = st.session_state.get("pasta_fonte", "")
        if pasta_atual:
            st.markdown(f'<div style="font-size:0.75rem;color:#9ECFB5;word-break:break-all;margin-bottom:0.5rem;">📂 {pasta_atual}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.75rem;color:rgba(255,255,255,0.35);">Não configurada</div>', unsafe_allow_html=True)

        if st.button("Procurar pasta...", width="stretch", key="sidebar_browse"):
            pasta_escolhida = _abrir_pasta_dialog()
            if pasta_escolhida:
                st.session_state["_pasta_sidebar_tmp"] = pasta_escolhida

        pasta_sb_tmp = st.session_state.get("_pasta_sidebar_tmp", "")
        if pasta_sb_tmp:
            st.markdown(f'<div style="font-size:0.72rem;color:#9ECFB5;margin:0.3rem 0;">{pasta_sb_tmp}</div>', unsafe_allow_html=True)
            if st.button("✅ Confirmar", type="primary", width="stretch", key="sidebar_confirmar"):
                with st.spinner("Carregando..."):
                    res = _carregar_pasta_fonte(pasta_sb_tmp)
                if "erro" in res:
                    st.error(res["erro"])
                else:
                    st.session_state["pasta_fonte"] = pasta_sb_tmp
                    st.session_state.pop("_pasta_sidebar_tmp", None)
                    st.success(f"✅ {len(res.get('carregados', []))} arquivo(s)")
                    st.rerun()

        # Botão Atualizar — relertura do disco sem mudar a pasta
        if pasta_atual and st.button("🔄 Atualizar Inputs", width="stretch", key="sidebar_atualizar"):
            with st.spinner("Atualizando..."):
                res = _carregar_pasta_fonte(pasta_atual)
            if "erro" in res:
                st.error(res["erro"])
            else:
                st.success(f"✅ {len(res.get('carregados', []))} arquivo(s) atualizados")
                st.rerun()

    # ── Comparar Exercícios ────────────────────────────
    st.markdown('<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;color:rgba(255,255,255,0.4);text-transform:uppercase;margin:0.8rem 0 0.4rem;">Análise</div>', unsafe_allow_html=True)
    with st.expander("📊 Comparar Exercícios"):
        _df_atual_cmp = st.session_state.get("df_resultado")
        if _df_atual_cmp is None:
            st.caption("Execute ou carregue um resultado na sessão atual para comparar.")
        else:
            _versoes_com_res = listar_versoes_com_resultado()
            _id_atual = (st.session_state.get("sessao_carregada") or {}).get("id", "")
            _versoes_com_res = [v for v in _versoes_com_res if v["id"] != _id_atual]

            if not _versoes_com_res:
                st.caption("Nenhuma outra sessão com resultado salvo encontrada.")
            else:
                _opcoes_cmp = {
                    f"{v.get('nome_sessao','?')} — {v.get('nome_versao','?')} ({str(v.get('criado_em',''))[:10]})": v["id"]
                    for v in _versoes_com_res
                }
                _sel_cmp = st.selectbox("Comparar com", list(_opcoes_cmp.keys()), key="cmp_sel_versao")
                if st.button("🔍 Abrir Comparação", type="primary", width="stretch", key="cmp_abrir"):
                    try:
                        _vid_cmp = _opcoes_cmp[_sel_cmp]
                        _dados_cmp = carregar_versao(_vid_cmp)
                        _df_cmp = _dados_cmp.get("df_resultado")
                        if _df_cmp is None:
                            st.error("Resultado não encontrado na versão selecionada.")
                        else:
                            _meta_at = st.session_state.get("sessao_carregada") or {}
                            _nome_at = f"{_meta_at.get('nome_sessao','Atual')} {_meta_at.get('nome_versao','')}"
                            _meta_cmp = _dados_cmp.get("meta") or {}
                            _nome_cmp = f"{_meta_cmp.get('nome_sessao','?')} {_meta_cmp.get('nome_versao','')}"
                            _dialog_comparar(_df_atual_cmp, _nome_at.strip(), _df_cmp, _nome_cmp.strip())
                    except Exception as _e:
                        st.error(f"Erro ao carregar: {_e}")

    # ── Configurações ──────────────────────────────────
    st.markdown('<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.1em;color:rgba(255,255,255,0.4);text-transform:uppercase;margin:0.8rem 0 0.4rem;">Configurações</div>', unsafe_allow_html=True)

    mes_base = st.date_input("Mês Base", value=date.today().replace(day=1))
    st.session_state["mes_base_config"] = str(mes_base)
    visao = st.selectbox("Visão", ["LOCAL", "IFRS17", "Ambas"], key="visao_sel")

    if visao in ["IFRS17", "Ambas"]:
        usar_paa = st.checkbox("PAA (contratos ≤ 1 ano)", value=True, key="usar_paa_sel")
        taxa_desconto = st.number_input("Taxa Desconto (a.a.)", 0.0, 0.5, 0.0, 0.01, format="%.3f", key="taxa_desconto_sel")
        percentual_ra = st.number_input("Risk Adjustment (%)", 0.0, 0.5, 0.05, 0.01, format="%.3f", key="percentual_ra_sel")
    else:
        usar_paa = True
        taxa_desconto = 0.0
        percentual_ra = 0.05
    # Persiste no session_state para o auto-save
    st.session_state["_sp_visao"] = visao
    st.session_state["_sp_usar_paa"] = usar_paa
    st.session_state["_sp_taxa"] = taxa_desconto
    st.session_state["_sp_pra"] = percentual_ra

    # ── Ações ──────────────────────────────────────────
    st.markdown('<div style="height:1px;background:rgba(255,255,255,0.08);margin:1rem 0 0.8rem;"></div>', unsafe_allow_html=True)
    if st.button("↩  Trocar Sessão", width="stretch"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.markdown('<div style="text-align:center;font-size:0.65rem;color:rgba(255,255,255,0.22);margin-top:0.5rem;">Budget Engine v1.0</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────
# ── Header banner ──────────────────────────────────────
_meta_h = st.session_state.get("sessao_carregada") or {}
_h_sessao = _meta_h.get("nome_sessao") or _meta_h.get("nome", "—")
_h_versao = _meta_h.get("nome_versao") or ""
_h_visao  = st.session_state.get("visao_sel", "LOCAL")
st.markdown(f"""
<div style="background:linear-gradient(135deg,#003D22 0%,#00965E 100%);
            border-radius:10px;padding:1rem 1.5rem;margin-bottom:1rem;
            display:flex;align-items:center;justify-content:space-between;
            box-shadow:0 4px 16px rgba(0,79,48,0.25);">
    <div>
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.18em;
                    color:rgba(255,255,255,0.5);text-transform:uppercase;margin-bottom:2px;">
            Budget Engine
        </div>
        <div style="font-size:1.4rem;font-weight:700;color:#FFFFFF;line-height:1.1;letter-spacing:-0.01em;">
            Budget Engine
        </div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:0.7rem;color:rgba(255,255,255,0.45);margin-bottom:2px;">Sessão</div>
        <div style="font-size:0.92rem;font-weight:700;color:#FFFFFF;">{_h_sessao}</div>
        {"" if not _h_versao else f'<div style="font-size:0.75rem;color:rgba(255,255,255,0.6);">{_h_versao}</div>'}
    </div>
</div>
""", unsafe_allow_html=True)

tab0, tabDQ, tab1, tab2, tab3, tab4, tab5, tabAudit, tab6 = st.tabs([
    "💾 Sessões",
    "🔍 Data Quality",
    "📁 Inputs",
    "📐 Hipóteses",
    "🔧 Variáveis Custom",
    "▶️ Executar",
    "📊 Resultado",
    "🔎 Auditoria",
    "📖 Guideline"
])


# ═══════════════════════════════════════════════════════
# TAB 0 — VERSÕES DA SESSÃO
# ═══════════════════════════════════════════════════════
with tab0:
    meta_atual = st.session_state.get("sessao_carregada") or {}
    _sessao_raiz_id = meta_atual.get("sessao_raiz_id") or meta_atual.get("id")
    _nome_sessao = meta_atual.get("nome_sessao") or meta_atual.get("nome", "—")
    _version_id_atual = meta_atual.get("id")
    _autor_def = meta_atual.get("autor", "")

    st.header(f"💾 Versões — {_nome_sessao}")
    st.caption("Use **Salvar** para sobrescrever a versão atual, ou **Nova Versão** para criar um novo snapshot dentro desta sessão. Para mudar de sessão, use **Trocar Sessão** no painel esquerdo.")

    # ── Lista de versões da sessão ativa ───────────────
    _versoes = listar_versoes(_sessao_raiz_id) if _sessao_raiz_id else []

    if not _versoes:
        st.info("Nenhuma versão salva ainda. Use **Salvar** abaixo para criar a primeira.")
    else:
        st.subheader("Versões salvas")
        for _v in reversed(_versoes):
            _is_ativa = _v["id"] == _version_id_atual
            _nome_v = _v.get("nome_versao") or _v.get("nome", "—")
            _tag = " 🟢 **ativa**" if _is_ativa else ""
            with st.expander(
                f"{'📌 ' if _is_ativa else '📄 '}{_nome_v} — {_v.get('criado_em','')[:16]}{_tag}",
                expanded=_is_ativa
            ):
                _col_i1, _col_i2 = st.columns(2)
                with _col_i1:
                    st.markdown(f"**Autor:** {_v.get('autor', '—')}")
                    if _v.get("descricao"):
                        st.caption(_v["descricao"])
                with _col_i2:
                    _col_v1, _col_v2 = st.columns(2)
                    with _col_v1:
                        if not _is_ativa:
                            if st.button("📂 Ativar", key=f"ativar_v_{_v['id']}",
                                         width="stretch", type="primary"):
                                with st.spinner("Carregando versão..."):
                                    _dados = carregar_sessao(_v["id"])
                                    _restaurar_sessao(_dados)
                                st.rerun()
                        else:
                            st.success("Ativa")
                    with _col_v2:
                        if st.button("⬇️ ZIP", key=f"zip_v_{_v['id']}",
                                     width="stretch"):
                            _zb = exportar_sessao_zip(_v["id"])
                            st.download_button("📦", _zb, f"{_v['id']}.zip",
                                               "application/zip",
                                               key=f"dl_v_{_v['id']}")

    # ── Salvar versão atual (sobrescreve) ──────────────
    st.markdown("---")
    st.subheader("💾 Salvar")
    st.caption("Sobrescreve a versão atual com as configurações correntes.")

    _col_s1, _col_s2 = st.columns(2)
    with _col_s1:
        _nome_ver_save = st.text_input(
            "Nome da versão",
            value=meta_atual.get("nome_versao") or meta_atual.get("nome", ""),
            key="sv_nome_ver"
        )
        _autor_save = st.text_input("Autor", value=_autor_def, key="sv_autor")
    with _col_s2:
        _desc_save = st.text_area("Descrição", height=100, key="sv_desc",
                                   placeholder="ex: Budget base Jan/26")

    if st.button("💾 Salvar", type="primary", width="stretch"):
        if not _nome_ver_save.strip():
            st.warning("Digite um nome.")
        else:
            with st.spinner("Salvando..."):
                _sid = salvar_versao(
                    nome_sessao=_nome_sessao,
                    nome_versao=_nome_ver_save.strip(),
                    descricao=_desc_save,
                    autor=_autor_save,
                    sessao_raiz_id=_sessao_raiz_id,
                    mes_base=str(mes_base),
                    visao=visao,
                    usar_paa=usar_paa,
                    taxa_desconto=taxa_desconto,
                    percentual_ra=percentual_ra,
                    horizonte_por_produto=st.session_state.get("horizonte_por_produto", {"default": 12}),
                    max_meses_total=int(st.session_state.get("max_meses_total", 120)),
                    pasta_fonte=st.session_state.get("pasta_fonte", ""),
                    df_sinistros=st.session_state.get("sin_manual"),
                    df_comissao=st.session_state.get("com_manual"),
                    df_gastos=st.session_state.get("gas_manual"),
                    df_premissas_proj=st.session_state.get("df_premissas_proj"),
                    stock_bytes=st.session_state.get("stock_bytes_loaded"),
                    nb_bytes=st.session_state.get("nb_bytes_loaded"),
                    nos_custom=st.session_state.get("nos_custom", []),
                    version_id_fixo=_version_id_atual,
                    fallbacks=_coletar_fallbacks_estado(),
                    df_fallback_curva=st.session_state.get("fallback_curva"),
                    df_fallback_curva_sav=st.session_state.get("fallback_curva_savings"),
                )
                st.session_state["sessao_carregada"] = {
                    **meta_atual,
                    "id": _sid,
                    "nome_versao": _nome_ver_save.strip(),
                    "descricao": _desc_save,
                    "autor": _autor_save,
                    "criado_em": datetime.now().isoformat(),
                    "sessao_raiz_id": _sessao_raiz_id,
                    "nome_sessao": _nome_sessao,
                }
                # Preserva resultado calculado no zip recém-criado
                _df_res_save = st.session_state.get("df_resultado")
                if _df_res_save is not None:
                    try:
                        salvar_resultado_na_versao(
                            _sid, _df_res_save,
                            st.session_state.get("df_auditoria"),
                        )
                    except Exception:
                        pass
            st.success(f"✅ '{_nome_ver_save}' salva!")
            st.rerun()

    # ── Salvar nova versão (dentro da mesma sessão) ────
    st.markdown("---")
    st.subheader("🆕 Salvar como Nova Versão")
    st.caption("Cria um novo snapshot dentro desta sessão. A versão atual **não é alterada**.")

    if not st.session_state.get("_nova_versao_aberta"):
        if st.button("🆕 Nova Versão...", width="stretch"):
            st.session_state["_nova_versao_aberta"] = True
            st.rerun()
    else:
        _col_n1, _col_n2 = st.columns(2)
        with _col_n1:
            _nome_nova_ver = st.text_input("Nome da nova versão *",
                                            placeholder="ex: Conservador",
                                            key="sv_nova_nome")
            _autor_nova_ver = st.text_input("Autor", value=_autor_def, key="sv_nova_autor")
        with _col_n2:
            _desc_nova_ver = st.text_area("Descrição", height=100, key="sv_nova_desc",
                                           placeholder="ex: Versão com sinistros conservadores")

        _col_nb1, _col_nb2 = st.columns(2)
        with _col_nb1:
            if st.button("💾 Salvar Nova Versão", type="primary", width="stretch"):
                if not _nome_nova_ver.strip():
                    st.warning("Digite um nome.")
                else:
                    with st.spinner("Salvando nova versão..."):
                        _novo_sid = salvar_versao(
                            nome_sessao=_nome_sessao,
                            nome_versao=_nome_nova_ver.strip(),
                            descricao=_desc_nova_ver,
                            autor=_autor_nova_ver,
                            sessao_raiz_id=_sessao_raiz_id,
                            mes_base=str(mes_base),
                            visao=visao,
                            usar_paa=usar_paa,
                            taxa_desconto=taxa_desconto,
                            percentual_ra=percentual_ra,
                            horizonte_por_produto=st.session_state.get("horizonte_por_produto", {"default": 12}),
                            max_meses_total=int(st.session_state.get("max_meses_total", 120)),
                            pasta_fonte=st.session_state.get("pasta_fonte", ""),
                            df_sinistros=st.session_state.get("sin_manual"),
                            df_comissao=st.session_state.get("com_manual"),
                            df_gastos=st.session_state.get("gas_manual"),
                            df_premissas_proj=st.session_state.get("df_premissas_proj"),
                            stock_bytes=st.session_state.get("stock_bytes_loaded"),
                            nb_bytes=st.session_state.get("nb_bytes_loaded"),
                            nos_custom=st.session_state.get("nos_custom", []),
                            fallbacks=_coletar_fallbacks_estado(),
                            df_fallback_curva=st.session_state.get("fallback_curva"),
                            df_fallback_curva_sav=st.session_state.get("fallback_curva_savings"),
                        )
                        st.session_state["sessao_carregada"] = {
                            **meta_atual,
                            "id": _novo_sid,
                            "nome_versao": _nome_nova_ver.strip(),
                            "descricao": _desc_nova_ver,
                            "autor": _autor_nova_ver,
                            "criado_em": datetime.now().isoformat(),
                            "sessao_raiz_id": _sessao_raiz_id,
                            "nome_sessao": _nome_sessao,
                        }
                        # Preserva resultado calculado no zip recém-criado
                        _df_res_nv = st.session_state.get("df_resultado")
                        if _df_res_nv is not None:
                            try:
                                salvar_resultado_na_versao(
                                    _novo_sid, _df_res_nv,
                                    st.session_state.get("df_auditoria"),
                                )
                            except Exception:
                                pass
                    st.session_state.pop("_nova_versao_aberta", None)
                    st.success(f"✅ Nova versão '{_nome_nova_ver}' criada!")
                    st.rerun()
        with _col_nb2:
            if st.button("↩️ Cancelar", width="stretch"):
                st.session_state.pop("_nova_versao_aberta", None)
                st.rerun()

    # ── Importar ZIP ───────────────────────────────────
    st.markdown("---")
    with st.expander("📥 Importar sessão de outro ambiente"):
        zip_import = st.file_uploader("Upload do arquivo .zip", type=["zip"])
        nome_import = st.text_input("Nome para a sessão importada",
                                     placeholder="ex: Budget 202601 (recebido)")
        if zip_import and st.button("📥 Importar", type="primary"):
            novo_id = importar_sessao_zip(zip_import.read(), nome_import or None)
            st.success(f"✅ Sessão importada com ID: `{novo_id}`")
            st.rerun()



# ═══════════════════════════════════════════════════════
# TAB DQ — DATA QUALITY
# ═══════════════════════════════════════════════════════
with tabDQ:
    st.header("🔍 Data Quality — Validação dos Inputs")
    st.caption("Valida todos os arquivos da pasta de inputs: existência, colunas, tipos e valores.")

    pasta_dq = st.session_state.get("pasta_fonte", "")
    if not pasta_dq:
        st.warning("Nenhuma pasta de inputs configurada. Configure na sidebar.")
        st.stop()

    if st.button("▶️ Executar Validação", type="primary"):
        st.session_state["_dq_run"] = True

    if not st.session_state.get("_dq_run"):
        st.info("Clique em **Executar Validação** para checar os arquivos.")
    else:
        from pathlib import Path as _Path
        import pandas as _pd
        import numpy as _np
        from io import BytesIO as _BytesIO

        _pasta = _Path(pasta_dq)

        # ── Esquemas esperados ──────────────────────────────
        _COLS_STOCK = {
            "fonte": "str", "safra": "str", "data_fim_mes": "date",
            "data_ini_mes": "date", "produto_atuarial": "int",
            "businessline": "str", "safra_venda": "str", "tipo_premio": "str",
            "valor_premio_emitido": "float", "valor_comissao": "float",
            "data_inicio_vigencia": "date", "data_fim_vigencia": "date",
            "quantidade_certificados": "int",
        }
        _COLS_SINISTROS = {
            "produto_atuarial": "int", "businessline": "str",
            "tipo_hipotese": "str", "valor": "float",
            "frequencia": "float", "severidade_media": "float",
            "periodo_inicio": "str", "periodo_fim": "str",
        }
        _COLS_COMISSAO = {
            "produto_atuarial": "int", "businessline": "str",
            "tipo_regra": "str", "valor": "float",
            "periodo_inicio": "str", "periodo_fim": "str",
        }
        _COLS_GASTOS = {
            "produto_atuarial": "int", "businessline": "str",
            "tipo_gasto": "str", "tipo_regra": "str", "valor": "float",
            "periodo_inicio": "str", "periodo_fim": "str",
        }
        _ARQUIVOS = {
            "stock.csv":         (_COLS_STOCK,     True),
            "new_business.csv":  (_COLS_STOCK,     True),
            "sinistros.csv":     (_COLS_SINISTROS, True),
            "comissao.csv":      (_COLS_COMISSAO,  True),
            "gastos.csv":        (_COLS_GASTOS,    True),
            "persistencia.xlsx": ({},              False),
        }

        _VALID_TIPO_HIPOTESE = {"percentual_premio_ganho", "valor_fixo", "frequencia_severidade"}
        _VALID_TIPO_REGRA    = {"percentual_premio_emitido", "percentual_premio_ganho", "valor_fixo"}

        def _checar_tipos(df, esquema, nome_arquivo):
            erros = []
            for col, tipo in esquema.items():
                if col not in df.columns:
                    continue
                serie = df[col]
                if tipo in ("float", "int"):
                    # Normaliza separador decimal (vírgula → ponto) antes de converter
                    serie_norm = serie.str.replace(",", ".", regex=False) if serie.dtype == object else serie
                    nao_num = _pd.to_numeric(serie_norm, errors="coerce").isna() & serie.notna()
                    n = nao_num.sum()
                    if n > 0:
                        exemplos = serie[nao_num].head(3).tolist()
                        erros.append(f"**{col}**: {n} valor(es) não-numérico(s) — ex: {exemplos}")
                elif tipo == "date":
                    nao_data = _pd.to_datetime(serie, errors="coerce", dayfirst=True).isna() & serie.notna()
                    n = nao_data.sum()
                    if n > 0:
                        exemplos = serie[nao_data].head(3).tolist()
                        erros.append(f"**{col}**: {n} data(s) inválida(s) — ex: {exemplos}")
            return erros

        def _checar_nulos(df, esquema):
            resultado = {}
            for col in esquema:
                if col not in df.columns:
                    continue
                n_nulos = df[col].isna().sum()   # NaN/None — 0 é diferente de nulo
                if n_nulos > 0:
                    resultado[col] = n_nulos
            return resultado

        # ── Resumo geral ────────────────────────────────────
        _score_total = 0
        _score_max   = 0

        for _arq, (_esquema, _obrigatorio) in _ARQUIVOS.items():
            _caminho = _pasta / _arq
            _existe  = _caminho.exists()
            _score_max += 1

            with st.expander(
                f"{'✅' if _existe else ('❌' if _obrigatorio else '⚠️')}  **{_arq}**"
                + ("" if _existe else " — arquivo não encontrado"),
                expanded=not _existe and _obrigatorio
            ):
                if not _existe:
                    if _obrigatorio:
                        st.error(f"Arquivo obrigatório não encontrado: `{_caminho}`")
                    else:
                        st.info("Arquivo opcional não presente (ok).")
                    continue

                _score_total += 1

                # Lê o arquivo
                try:
                    if _arq.endswith(".xlsx"):
                        _df = _pd.read_excel(str(_caminho))
                        st.success(f"Lido com sucesso — {len(_df)} linhas, {len(_df.columns)} colunas")
                        continue
                    else:
                        _df = _pd.read_csv(str(_caminho), sep=";", decimal=",", dtype=str)
                except Exception as _e:
                    st.error(f"Erro ao ler arquivo: {_e}")
                    continue

                st.markdown(f"**{len(_df):,} linhas** | **{len(_df.columns)} colunas**")

                # Colunas ausentes
                _cols_esperadas = set(_esquema.keys())
                _cols_presentes = set(c.strip().lower() for c in _df.columns)
                _df.columns     = [c.strip().lower() for c in _df.columns]
                _faltando = _cols_esperadas - _cols_presentes
                _extras   = _cols_presentes - _cols_esperadas

                col_dq1, col_dq2 = st.columns(2)
                with col_dq1:
                    if _faltando:
                        st.error(f"**Colunas ausentes ({len(_faltando)}):**\n" +
                                 "\n".join(f"- `{c}`" for c in sorted(_faltando)))
                    else:
                        st.success("Todas as colunas obrigatórias presentes ✅")
                with col_dq2:
                    if _extras:
                        st.info(f"**Colunas extras ({len(_extras)})** (não obrigatórias):\n" +
                                "\n".join(f"- `{c}`" for c in sorted(_extras)))

                # Nulos (0 ≠ nulo)
                _nulos = _checar_nulos(_df, _esquema)
                if _nulos:
                    st.warning("**Valores nulos (vazios) por coluna** — atenção: 0 ≠ vazio")
                    _df_nulos = _pd.DataFrame(
                        [{"Coluna": c, "Nulos": n, "% do total": f"{n/len(_df)*100:.1f}%"}
                         for c, n in _nulos.items()]
                    )
                    st.dataframe(_df_nulos, width="stretch", hide_index=True)
                else:
                    st.success("Nenhum valor nulo nas colunas obrigatórias ✅")

                # Tipos de dados
                _erros_tipo = _checar_tipos(_df, _esquema, _arq)
                if _erros_tipo:
                    st.error("**Erros de tipo de dado:**")
                    for _e in _erros_tipo:
                        st.markdown(f"- {_e}")
                else:
                    st.success("Tipos de dados OK ✅")

                # Validações de domínio específicas
                if _arq == "sinistros.csv" and "tipo_hipotese" in _df.columns:
                    _inv = _df[~_df["tipo_hipotese"].isin(_VALID_TIPO_HIPOTESE)]
                    if len(_inv) > 0:
                        st.warning(f"**tipo_hipotese**: {len(_inv)} valor(es) inválido(s). "
                                   f"Esperado: {_VALID_TIPO_HIPOTESE}\n"
                                   f"Encontrado: {_inv['tipo_hipotese'].unique().tolist()}")

                if _arq in ("comissao.csv", "gastos.csv") and "tipo_regra" in _df.columns:
                    _inv = _df[~_df["tipo_regra"].isin(_VALID_TIPO_REGRA)]
                    if len(_inv) > 0:
                        st.warning(f"**tipo_regra**: {len(_inv)} valor(es) inválido(s). "
                                   f"Esperado: {_VALID_TIPO_REGRA}")

                if _arq in ("stock.csv", "new_business.csv") and "tipo_premio" in _df.columns:
                    _inv = _df[~_df["tipo_premio"].str.upper().isin({"PM", "PU"})]
                    if len(_inv) > 0:
                        st.warning(f"**tipo_premio**: valores fora de PM/PU: "
                                   f"{_inv['tipo_premio'].unique().tolist()}")

                # Preview
                with st.expander("👁️ Preview (5 primeiras linhas)"):
                    st.dataframe(_df.head(5), width="stretch")

        # Placar final
        st.markdown("---")
        _pct = int(_score_total / _score_max * 100) if _score_max > 0 else 0
        if _pct == 100:
            st.success(f"✅ **Todos os arquivos obrigatórios encontrados e validados** ({_score_total}/{_score_max})")
        else:
            st.error(f"❌ **{_score_total}/{_score_max} arquivos OK** — revise os itens acima antes de executar o cálculo.")

        # ── Verificação cruzada: sobreposição Stock × New Business ──
        # Referências: mes_base (foto do stock) vs menor safra_venda do NB
        _f_nb = _pasta / "new_business.csv"
        _mes_base_dq = st.session_state.get("mes_base_config") or str(date.today().replace(day=1))
        if _f_nb.exists():
            try:
                _df_nb2 = _pd.read_csv(str(_f_nb), sep=";", decimal=",", dtype=str)
                _df_nb2.columns = [c.strip().lower() for c in _df_nb2.columns]

                _dt_mes_base = _pd.to_datetime(_mes_base_dq, errors="coerce")
                _col_nb = next((c for c in ["safra_venda", "data_ini_mes",
                                             "data_inicio_vigencia"] if c in _df_nb2.columns), None)

                if _col_nb and _pd.notna(_dt_mes_base):
                    _min_nb = _pd.to_datetime(_df_nb2[_col_nb], dayfirst=True, errors="coerce").min()

                    st.markdown("---")
                    st.markdown("**🔀 Verificação cruzada — Stock (Mês Base) × New Business (menor safra_venda)**")
                    if _pd.notna(_min_nb):
                        if _min_nb <= _dt_mes_base:
                            st.error(
                                f"⚠️ **Sobreposição detectada!** "
                                f"A menor `safra_venda` do NB é **{_min_nb.strftime('%b/%Y')}**, "
                                f"mas o Mês Base do Stock é **{_dt_mes_base.strftime('%b/%Y')}**. "
                                f"O NB deve começar após o Mês Base."
                            )
                        else:
                            _gap = (_min_nb.year - _dt_mes_base.year) * 12 + (_min_nb.month - _dt_mes_base.month)
                            if _gap > 1:
                                st.warning(
                                    f"⚠️ Gap de **{_gap - 1} mês(es)** entre o Mês Base do Stock "
                                    f"({_dt_mes_base.strftime('%b/%Y')}) e a menor safra_venda do NB "
                                    f"({_min_nb.strftime('%b/%Y')}). Verifique se é intencional."
                                )
                            else:
                                st.success(
                                    f"✅ Mês Base do Stock: **{_dt_mes_base.strftime('%b/%Y')}** · "
                                    f"Menor safra_venda NB: **{_min_nb.strftime('%b/%Y')}** — OK."
                                )
            except Exception:
                pass

        # ── Validação de duplicatas em Stock e NB ──────────
        _CHAVES_DQ = ["safra", "produto_atuarial", "businessline", "safra_venda",
                      "tipo_premio", "data_inicio_vigencia", "data_fim_vigencia",
                      "mes_projecao"]
        st.markdown("---")
        st.markdown("**🔁 Validação de Duplicatas**")
        st.caption("Registros com mesma combinação de chaves devem ser agrupados em uma única linha para evitar duplicação de valores.")
        for _arq_dup in ["stock.csv", "new_business.csv"]:
            _path_dup = _pasta / _arq_dup
            if not _path_dup.exists():
                continue
            try:
                _df_dup = _pd.read_csv(str(_path_dup), sep=";", decimal=",", dtype=str)
                _df_dup.columns = [c.strip().lower().replace(" ", "_") for c in _df_dup.columns]
                _chaves_presentes = [c for c in _CHAVES_DQ if c in _df_dup.columns]
                if len(_chaves_presentes) < 2:
                    continue
                _dups = _df_dup[_df_dup.duplicated(subset=_chaves_presentes, keep=False)]
                if _dups.empty:
                    st.success(f"✅ **{_arq_dup}** — nenhuma combinação de chaves duplicada.")
                else:
                    _n_grupos = _dups.groupby(_chaves_presentes).ngroups
                    with st.expander(f"⚠️ **{_arq_dup}** — {len(_dups)} linhas em {_n_grupos} grupo(s) duplicado(s)", expanded=True):
                        st.warning(
                            "Estas combinações de chaves aparecem mais de uma vez. "
                            "Se os valores (prêmio, certificados etc.) forem diferentes, os números serão somados duplicando os totais. "
                            "Recomendamos juntar tudo em uma única linha por combinação de chaves."
                        )
                        st.dataframe(_dups[_chaves_presentes + [c for c in _df_dup.columns if c not in _chaves_presentes][:4]]
                                     .head(20), width="stretch", hide_index=True)
            except Exception as _ex_dup:
                st.warning(f"Não foi possível validar {_arq_dup}: {_ex_dup}")


# ═══════════════════════════════════════════════════════
# TAB 1 — INPUTS
# ═══════════════════════════════════════════════════════
with tab1:
    st.header("📁 Inputs de Dados")

    # Status da pasta fonte
    pasta_atual = st.session_state.get("pasta_fonte", "")
    if pasta_atual:
        st.info(f"📂 Pasta de inputs: `{pasta_atual}` — você pode sobrescrever qualquer arquivo abaixo.")
    else:
        st.warning("Pasta de inputs não configurada. Configure na sidebar ou faça upload manual.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📦 Stock")
        # Mostra status do carregamento automático
        if "stock_bytes_loaded" in st.session_state:
            try:
                df_prev = pd.read_csv(BytesIO(st.session_state["stock_bytes_loaded"]),
                                      sep=";", decimal=",", nrows=5)
                st.success(f"✅ stock.csv carregado ({len(df_prev.columns)} colunas)")
                st.dataframe(df_prev, width="stretch")
            except Exception as e:
                st.error(f"Erro ao ler stock: {e}")

        stock_file = st.file_uploader("Substituir Stock CSV", type=["csv"],
                                       key="stock_upload")
        if stock_file:
            st.session_state["stock_file"] = stock_file
            data = stock_file.read()
            st.session_state["stock_bytes_loaded"] = data
            df_prev = pd.read_csv(BytesIO(data), sep=";", decimal=",", nrows=5)
            st.success(f"✅ {stock_file.name} carregado")
            st.dataframe(df_prev, width="stretch")
            # Limpa premissas para reconstruir
            st.session_state.pop("df_premissas_proj", None)

    with col2:
        st.subheader("🆕 New Business")
        if "nb_bytes_loaded" in st.session_state:
            try:
                df_prev = pd.read_csv(BytesIO(st.session_state["nb_bytes_loaded"]),
                                      sep=";", decimal=",", nrows=5)
                st.success(f"✅ new_business.csv carregado ({len(df_prev.columns)} colunas)")
                st.dataframe(df_prev, width="stretch")
            except Exception as e:
                st.error(f"Erro ao ler new_business: {e}")

        nb_file = st.file_uploader("Substituir New Business CSV", type=["csv"],
                                    key="nb_upload")
        if nb_file:
            st.session_state["nb_file"] = nb_file
            data = nb_file.read()
            st.session_state["nb_bytes_loaded"] = data
            df_prev = pd.read_csv(BytesIO(data), sep=";", decimal=",", nrows=5)
            st.success(f"✅ {nb_file.name} carregado")
            st.dataframe(df_prev, width="stretch")
            st.session_state.pop("df_premissas_proj", None)

    # ── Horizonte de Projeção — TABELA ────────────────
    st.markdown("---")
    st.subheader("🗓️ Horizonte de Projeção por Produto")
    _aviso_sem_pasta()
    st.info(
        "Tabela gerada automaticamente a partir do **stock** e **new business** carregados. "
        "Ajuste os meses por produto/business line — as alterações são salvas automaticamente."
    )

    df_hor = _build_horizonte_df()

    tem_dados = not df_hor.empty
    if not tem_dados:
        st.warning("Carregue stock ou new business para preencher automaticamente. "
                   "Ou adicione linhas manualmente abaixo.")

    # Coluna tipo é somente leitura (colorida para identificação)
    df_editado = st.data_editor(
        df_hor,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "categoria": st.column_config.SelectboxColumn(
                "Categoria",
                options=["Protection", "Savings"],
                required=True,
                help="Protection = seguro tradicional com vigência. Savings = previdência/capitalização sem prazo fixo.",
            ),
            "produto_atuarial": st.column_config.TextColumn("Produto Atuarial"),
            "businessline": st.column_config.TextColumn("Business Line"),
            "tipo": st.column_config.SelectboxColumn(
                "Tipo",
                options=["Stock", "New Business"],
                required=True,
            ),
            "meses": st.column_config.NumberColumn(
                "Duração Certificado",
                min_value=0,
                max_value=600,
                step=1,
                format="%d meses",
                help="Savings: deixe 0 (sem duração fixa). Protection: meses do ciclo de renovação.",
            ),
        },
        key="hor_editor",
    )

    # Auto-save horizonte sempre que houver alteração
    if not df_editado.empty:
        st.session_state["df_premissas_proj"] = df_editado.copy()
        st.session_state["horizonte_por_produto"] = _horizonte_dict(df_editado)
        _hash_hor = int(pd.util.hash_pandas_object(df_editado, index=False).sum())
        if st.session_state.get("_hash_hor_saved") != _hash_hor:
            meta_c = st.session_state.get("sessao_carregada", {})
            sid = (meta_c or {}).get("id", "sem_sessao")
            _salvar_premissas(df_editado, sid)
            st.session_state["_hash_hor_saved"] = _hash_hor

    if "df_premissas_proj" in st.session_state:
        csv_prem = st.session_state["df_premissas_proj"].to_csv(
            sep=";", decimal=",", index=False, encoding="utf-8-sig"
        ).encode("utf-8-sig")
        st.download_button("⬇️ Baixar premissas_proj.csv", csv_prem,
                           "premissas_proj.csv", "text/csv",
                           width="stretch")


# ═══════════════════════════════════════════════════════
# TAB 2 — HIPÓTESES
# ═══════════════════════════════════════════════════════
with tab2:
    st.header("📐 Hipóteses de Cálculo")

    pasta_atual = st.session_state.get("pasta_fonte", "")
    if pasta_atual:
        st.info(f"📂 Carregado de `{pasta_atual}` — substitua individualmente se necessário.")

    sub1, sub2, sub3, sub4, sub5 = st.tabs([
        "🏥 Sinistros", "💰 Comissão", "💸 Gastos & Other NBI", "📉 Persistência", "💰 Hip. Savings"
    ])

    # ── Sinistros ──────────────────────────────────────
    with sub1:
        st.subheader("Hipóteses de Sinistros")
        _aviso_sem_pasta()
        sin_file = st.file_uploader("Substituir Hipóteses Sinistros CSV",
                                     type=["csv"], key="sin")
        if sin_file:
            df_sin = pd.read_csv(sin_file, sep=";", decimal=",")
            st.session_state["sin_manual"] = df_sin
            st.success(f"✅ {sin_file.name} carregado")

        st.info(
            "**Como definir regras por período:**\n\n"
            "- Deixe `periodo_inicio` e `periodo_fim` **vazios** → regra vale para **todos os meses** (padrão global).\n"
            "- Preencha `periodo_inicio` e `periodo_fim` no formato `AAAA/MM` → regra sobrescreve o global naquele intervalo.\n"
            "- `periodo_fim` vazio = apenas o mês de `periodo_inicio`.\n\n"
            "**Exemplos:** `2026/01` → `2026/12` cobre o ano inteiro de 2026 · `2028/01` → vazio = só janeiro/2028"
        )
        st.markdown("**Editar hipóteses de sinistros:**")
        default_sin = st.session_state.get("sin_manual", pd.DataFrame({
            "produto_atuarial": [1001],
            "businessline": ["Personal Protection"],
            "tipo_hipotese": ["percentual_premio_ganho"],
            "valor": [0.40],
            "frequencia": [0.0],
            "severidade_media": [0.0],
            "periodo_inicio": [""],
            "periodo_fim": [""],
        }))
        if not isinstance(default_sin, pd.DataFrame):
            default_sin = pd.DataFrame(default_sin)
        edited = st.data_editor(default_sin, num_rows="dynamic",
                                width="stretch", key="sin_editor")
        st.session_state["sin_manual"] = edited
        _auto_salvar_csv(edited, "sinistros.csv", "_hash_sin")

        st.markdown("---")

        # ── Sync widget keys dos fallbacks ao restaurar sessão ────────────────
        # Roda uma única vez após restauração: garante que os checkboxes/selects
        # apareçam pré-setados mesmo que o Streamlit tenha limpado os widget keys
        # entre a restauração (gate) e o primeiro render do Tab 2.
        if st.session_state.pop("_needs_fb_sync", False):
            _FB_SYNC = {
                "sin_fallback":             [("ativo","sin_fb_ativo"),    ("tipo","sin_fb_tipo"),
                                             ("valor","sin_fb_valor"),    ("frequencia","sin_fb_freq"),
                                             ("severidade_media","sin_fb_sev")],
                "sin_fallback_savings":     [("ativo","sin_fb_sav_ativo"), ("tipo","sin_fb_sav_tipo"),
                                             ("valor","sin_fb_sav_valor")],
                "com_fallback":             [("ativo","com_fb_ativo"),    ("tipo","com_fb_tipo"),
                                             ("valor","com_fb_valor")],
                "com_fallback_savings":     [("ativo","com_fb_sav_ativo"), ("tipo","com_fb_sav_tipo"),
                                             ("valor","com_fb_sav_valor")],
                "gas_gastos_fallback":      [("ativo","gas_fb_ativo"),    ("tipo","gas_fb_tipo"),
                                             ("valor","gas_fb_valor")],
                "gas_othernbi_fallback":    [("ativo","nbi_fb_ativo"),    ("tipo","nbi_fb_tipo"),
                                             ("valor","nbi_fb_valor")],
                "gas_gastos_fallback_sav":  [("ativo","gas_fb_sav_ativo"), ("tipo","gas_fb_sav_tipo"),
                                             ("valor","gas_fb_sav_valor")],
                "gas_othernbi_fallback_sav":[("ativo","nbi_fb_sav_ativo"), ("tipo","nbi_fb_sav_tipo"),
                                             ("valor","nbi_fb_sav_valor")],
            }
            for _dk, _ws in _FB_SYNC.items():
                _fb_d = st.session_state.get(_dk, {})
                for _campo, _wkey in _ws:
                    if _campo in _fb_d:
                        st.session_state[_wkey] = _fb_d[_campo]

        _col_sin_p, _col_sin_s = st.columns(2)
        with _col_sin_p:
            st.markdown("**⚙️ Fallback Protection — sem hipótese de sinistros**")
            _fb_sin = st.session_state["sin_fallback"]
            _fb_sin["ativo"] = st.checkbox("Usar padrão (Protection)", value=_fb_sin["ativo"], key="sin_fb_ativo")
            if _fb_sin["ativo"]:
                _c1, _c2, _c3, _c4 = st.columns(4)
                with _c1:
                    _fb_sin["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "valor_fixo", "frequencia_severidade"],
                                                   index=["percentual_premio_ganho","valor_fixo","frequencia_severidade"].index(_fb_sin["tipo"]),
                                                   key="sin_fb_tipo")
                with _c2:
                    _fb_sin["valor"] = st.number_input("Valor / %", value=float(_fb_sin["valor"]),
                                                        format="%.4f", key="sin_fb_valor")
                if _fb_sin["tipo"] == "frequencia_severidade":
                    with _c3:
                        _fb_sin["frequencia"] = st.number_input("Frequência", value=float(_fb_sin["frequencia"]),
                                                                 format="%.4f", key="sin_fb_freq")
                    with _c4:
                        _fb_sin["severidade_media"] = st.number_input("Severidade Média", value=float(_fb_sin["severidade_media"]),
                                                                       format="%.2f", key="sin_fb_sev")
            st.session_state["sin_fallback"] = _fb_sin
        with _col_sin_s:
            st.markdown("**⚙️ Fallback Savings — sem hipótese de sinistros**")
            _fb_sin_s = st.session_state["sin_fallback_savings"]
            _fb_sin_s["ativo"] = st.checkbox("Usar padrão (Savings)", value=_fb_sin_s["ativo"], key="sin_fb_sav_ativo")
            if _fb_sin_s["ativo"]:
                _cs1, _cs2 = st.columns(2)
                with _cs1:
                    _fb_sin_s["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "valor_fixo", "frequencia_severidade"],
                                                     index=["percentual_premio_ganho","valor_fixo","frequencia_severidade"].index(_fb_sin_s["tipo"]),
                                                     key="sin_fb_sav_tipo")
                with _cs2:
                    _fb_sin_s["valor"] = st.number_input("Valor / %", value=float(_fb_sin_s["valor"]),
                                                          format="%.4f", key="sin_fb_sav_valor")
            st.session_state["sin_fallback_savings"] = _fb_sin_s
        st.markdown("---")
        _painel_sem_hipotese(
            st.session_state.get("sin_manual"), "sinistros", _fb_sin["ativo"],
            colunas_template=["produto_atuarial", "businessline", "tipo_hipotese", "valor", "frequencia", "severidade_media"],
            session_key="sin_manual"
        )

    # ── Comissão ───────────────────────────────────────
    with sub2:
        st.subheader("Hipóteses de Comissão")
        _aviso_sem_pasta()
        com_file = st.file_uploader("Substituir Hipóteses Comissão CSV",
                                     type=["csv"], key="com")
        if com_file:
            df_com = pd.read_csv(com_file, sep=";", decimal=",")
            st.session_state["com_manual"] = df_com
            st.success(f"✅ {com_file.name} carregado")

        st.info(
            "**Como definir regras por período:**\n\n"
            "- Deixe `periodo_inicio` e `periodo_fim` **vazios** → regra vale para **todos os meses** (padrão global).\n"
            "- Preencha `periodo_inicio` e `periodo_fim` no formato `AAAA/MM` → regra sobrescreve o global naquele intervalo.\n"
            "- `periodo_fim` vazio = apenas o mês de `periodo_inicio`.\n\n"
            "**Exemplos:** `2026/01` → `2026/12` cobre o ano inteiro de 2026 · `2028/01` → vazio = só janeiro/2028"
        )
        st.markdown("**Editar hipóteses de comissão:**")
        default_com = st.session_state.get("com_manual", pd.DataFrame({
            "produto_atuarial": [1001],
            "businessline": ["Personal Protection"],
            "tipo_regra": ["percentual_premio_emitido"],
            "valor": [0.15],
            "periodo_inicio": [""],
            "periodo_fim": [""],
        }))
        if not isinstance(default_com, pd.DataFrame):
            default_com = pd.DataFrame(default_com)
        edited_com = st.data_editor(default_com, num_rows="dynamic",
                                    width="stretch", key="com_editor")
        st.session_state["com_manual"] = edited_com
        _auto_salvar_csv(edited_com, "comissao.csv", "_hash_com")

        st.markdown("---")
        _col_com_p, _col_com_s = st.columns(2)
        with _col_com_p:
            st.markdown("**⚙️ Fallback Protection — sem hipótese de comissão**")
            _fb_com = st.session_state["com_fallback"]
            _fb_com["ativo"] = st.checkbox("Usar padrão (Protection)", value=_fb_com["ativo"], key="com_fb_ativo")
            if _fb_com["ativo"]:
                _c1, _c2 = st.columns(2)
                with _c1:
                    _fb_com["tipo"] = st.selectbox("Tipo", ["percentual_premio_emitido", "percentual_premio_ganho", "valor_fixo"],
                                                   index=["percentual_premio_emitido","percentual_premio_ganho","valor_fixo"].index(_fb_com["tipo"]),
                                                   key="com_fb_tipo")
                with _c2:
                    _fb_com["valor"] = st.number_input("Valor / %", value=float(_fb_com["valor"]),
                                                        format="%.4f", key="com_fb_valor")
            st.session_state["com_fallback"] = _fb_com
        with _col_com_s:
            st.markdown("**⚙️ Fallback Savings — sem hipótese de comissão**")
            _fb_com_s = st.session_state["com_fallback_savings"]
            _fb_com_s["ativo"] = st.checkbox("Usar padrão (Savings)", value=_fb_com_s["ativo"], key="com_fb_sav_ativo")
            if _fb_com_s["ativo"]:
                _cs1, _cs2 = st.columns(2)
                with _cs1:
                    _fb_com_s["tipo"] = st.selectbox("Tipo", ["percentual_premio_emitido", "percentual_premio_ganho", "valor_fixo"],
                                                     index=["percentual_premio_emitido","percentual_premio_ganho","valor_fixo"].index(_fb_com_s["tipo"]),
                                                     key="com_fb_sav_tipo")
                with _cs2:
                    _fb_com_s["valor"] = st.number_input("Valor / %", value=float(_fb_com_s["valor"]),
                                                          format="%.4f", key="com_fb_sav_valor")
            st.session_state["com_fallback_savings"] = _fb_com_s
        st.markdown("---")
        _painel_sem_hipotese(
            st.session_state.get("com_manual"), "comissão", _fb_com["ativo"],
            colunas_template=["produto_atuarial", "businessline", "tipo_regra", "valor"],
            session_key="com_manual"
        )

    # ── Gastos & Other NBI ─────────────────────────────
    with sub3:
        st.subheader("Hipóteses de Gastos & Other NBI")
        _aviso_sem_pasta()
        gas_file = st.file_uploader("Substituir Hipóteses Gastos CSV",
                                     type=["csv"], key="gas")
        if gas_file:
            df_gas = pd.read_csv(gas_file, sep=";", decimal=",")
            st.session_state["gas_manual"] = df_gas
            st.success(f"✅ {gas_file.name} carregado")

        st.info(
            "**Como definir regras por período:**\n\n"
            "- Deixe `periodo_inicio` e `periodo_fim` **vazios** → regra vale para **todos os meses** (padrão global).\n"
            "- Preencha `periodo_inicio` e `periodo_fim` no formato `AAAA/MM` → regra sobrescreve o global naquele intervalo.\n"
            "- `periodo_fim` vazio = apenas o mês de `periodo_inicio`.\n\n"
            "**Exemplos:** `2026/01` → `2026/12` cobre o ano inteiro de 2026 · `2028/01` → vazio = só janeiro/2028"
        )
        st.markdown("**Editar hipóteses de gastos:**")
        default_gas = st.session_state.get("gas_manual", pd.DataFrame({
            "produto_atuarial": [1001, 1001],
            "businessline": ["Personal Protection", "Personal Protection"],
            "tipo_gasto": ["gastos", "other_nbi"],
            "tipo_regra": ["percentual_premio_ganho", "percentual_premio_ganho"],
            "valor": [0.10, 0.05],
            "periodo_inicio": ["", ""],
            "periodo_fim": ["", ""],
        }))
        if not isinstance(default_gas, pd.DataFrame):
            default_gas = pd.DataFrame(default_gas)
        edited_gas = st.data_editor(default_gas, num_rows="dynamic",
                                    width="stretch", key="gas_editor")
        st.session_state["gas_manual"] = edited_gas
        _auto_salvar_csv(edited_gas, "gastos.csv", "_hash_gas")

        st.markdown("---")
        st.markdown("**⚙️ Fallback — sem hipótese de gastos / other NBI**")
        st.markdown("**Protection**")
        _col_g, _col_n = st.columns(2)
        with _col_g:
            st.markdown("*Gastos*")
            _fb_gas = st.session_state["gas_gastos_fallback"]
            _fb_gas["ativo"] = st.checkbox("Usar padrão gastos (Prot.)", value=_fb_gas["ativo"], key="gas_fb_ativo")
            if _fb_gas["ativo"]:
                _fb_gas["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "percentual_premio_emitido", "valor_fixo"],
                                               index=["percentual_premio_ganho","percentual_premio_emitido","valor_fixo"].index(_fb_gas["tipo"]),
                                               key="gas_fb_tipo")
                _fb_gas["valor"] = st.number_input("Valor / %", value=float(_fb_gas["valor"]),
                                                    format="%.4f", key="gas_fb_valor")
            st.session_state["gas_gastos_fallback"] = _fb_gas
        with _col_n:
            st.markdown("*Other NBI*")
            _fb_nbi = st.session_state["gas_othernbi_fallback"]
            _fb_nbi["ativo"] = st.checkbox("Usar padrão other NBI (Prot.)", value=_fb_nbi["ativo"], key="nbi_fb_ativo")
            if _fb_nbi["ativo"]:
                _fb_nbi["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "percentual_premio_emitido", "valor_fixo"],
                                               index=["percentual_premio_ganho","percentual_premio_emitido","valor_fixo"].index(_fb_nbi["tipo"]),
                                               key="nbi_fb_tipo")
                _fb_nbi["valor"] = st.number_input("Valor / %", value=float(_fb_nbi["valor"]),
                                                    format="%.4f", key="nbi_fb_valor")
            st.session_state["gas_othernbi_fallback"] = _fb_nbi
        st.markdown("**Savings**")
        _col_gs, _col_ns = st.columns(2)
        with _col_gs:
            st.markdown("*Gastos*")
            _fb_gas_s = st.session_state["gas_gastos_fallback_sav"]
            _fb_gas_s["ativo"] = st.checkbox("Usar padrão gastos (Sav.)", value=_fb_gas_s["ativo"], key="gas_fb_sav_ativo")
            if _fb_gas_s["ativo"]:
                _fb_gas_s["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "percentual_premio_emitido", "valor_fixo"],
                                                 index=["percentual_premio_ganho","percentual_premio_emitido","valor_fixo"].index(_fb_gas_s["tipo"]),
                                                 key="gas_fb_sav_tipo")
                _fb_gas_s["valor"] = st.number_input("Valor / %", value=float(_fb_gas_s["valor"]),
                                                      format="%.4f", key="gas_fb_sav_valor")
            st.session_state["gas_gastos_fallback_sav"] = _fb_gas_s
        with _col_ns:
            st.markdown("*Other NBI*")
            _fb_nbi_s = st.session_state["gas_othernbi_fallback_sav"]
            _fb_nbi_s["ativo"] = st.checkbox("Usar padrão other NBI (Sav.)", value=_fb_nbi_s["ativo"], key="nbi_fb_sav_ativo")
            if _fb_nbi_s["ativo"]:
                _fb_nbi_s["tipo"] = st.selectbox("Tipo", ["percentual_premio_ganho", "percentual_premio_emitido", "valor_fixo"],
                                                  index=["percentual_premio_ganho","percentual_premio_emitido","valor_fixo"].index(_fb_nbi_s["tipo"]),
                                                  key="nbi_fb_sav_tipo")
                _fb_nbi_s["valor"] = st.number_input("Valor / %", value=float(_fb_nbi_s["valor"]),
                                                      format="%.4f", key="nbi_fb_sav_valor")
            st.session_state["gas_othernbi_fallback_sav"] = _fb_nbi_s

        st.markdown("---")
        _hip_gas = st.session_state.get("gas_manual")
        _hip_gastos_only  = _hip_gas[_hip_gas["tipo_gasto"] == "gastos"]  if _hip_gas is not None and "tipo_gasto" in _hip_gas.columns else None
        _hip_othernbi_only = _hip_gas[_hip_gas["tipo_gasto"] == "other_nbi"] if _hip_gas is not None and "tipo_gasto" in _hip_gas.columns else None
        _painel_sem_hipotese(
            _hip_gastos_only, "gastos", _fb_gas["ativo"],
            colunas_template=["produto_atuarial", "businessline", "tipo_gasto", "tipo_regra", "valor"],
            session_key="gas_manual_gastos", save_key="gas_manual"
        )
        _painel_sem_hipotese(
            _hip_othernbi_only, "other NBI", _fb_nbi["ativo"],
            colunas_template=["produto_atuarial", "businessline", "tipo_gasto", "tipo_regra", "valor"],
            session_key="gas_manual_othernbi", save_key="gas_manual"
        )

    # ── Persistência ───────────────────────────────────
    with sub4:
        st.subheader("📉 Curvas de Persistência — Protection")
        st.info(
            "A curva define quantos % dos certificados ainda estão ativos em cada mês de vida. "
            "Carregada automaticamente de `persistencia.xlsx` na pasta de inputs."
        )

        curvas_carregadas = st.session_state.get("curvas_persistencia", {})
        if curvas_carregadas:
            st.success(f"✅ Curvas carregadas para {len(curvas_carregadas)} produto(s): "
                       f"{list(curvas_carregadas.keys())}")

        col_p1, col_p2 = st.columns([2, 1])

        with col_p1:
            persist_file = st.file_uploader(
                "Substituir Excel de Persistência (.xlsx)",
                type=["xlsx"], key="persist_upload",
            )
            if persist_file:
                try:
                    curvas_carregadas = carregar_persistencia_excel(persist_file)
                    st.session_state["curvas_persistencia"] = curvas_carregadas
                    st.success(f"✅ {persist_file.name} carregado — "
                               f"{len(curvas_carregadas)} produto(s)")
                except Exception as e:
                    st.error(f"Erro: {e}")

            if curvas_carregadas:
                produto_preview = st.selectbox("Visualizar curva do produto",
                                               list(curvas_carregadas.keys()),
                                               key="preview_prod")
                if produto_preview:
                    import plotly.express as px
                    curva_v = curvas_carregadas[produto_preview]
                    df_curva = pd.DataFrame({
                        "Mês de Vida": list(curva_v.keys()),
                        "Persistência (%)": [v * 100 for v in curva_v.values()]
                    })
                    fig_p = px.line(df_curva, x="Mês de Vida", y="Persistência (%)",
                                    title=f"Curva — Produto {produto_preview}", markers=True)
                    fig_p.add_hline(y=0, line_dash="dash", line_color="red")
                    st.plotly_chart(fig_p, width="stretch")

        with col_p2:
            st.markdown("**📥 Download Template**")
            if st.button("Gerar Template Excel", width="stretch"):
                import tempfile
                tmp = tempfile.mktemp(suffix=".xlsx")
                gerar_template_persistencia([1001, 1002, 2001, 2002, 3001],
                                             n_meses=36, filepath=tmp)
                with open(tmp, "rb") as f:
                    st.download_button("⬇️ Baixar template", f.read(),
                                       "persistencia_template.xlsx",
                                       width="stretch")
                os.unlink(tmp)

            st.markdown("---")
            st.markdown("**⚙️ Fallback (sem curva definida)**")
            usar_fallback = st.checkbox("Usar curva padrão para produtos sem curva", value=True,
                                        key="persist_usar_fallback")
            if usar_fallback:
                dec_fallback = st.number_input("Decaimento mensal (%)", 0.0, 10.0, 2.0, 0.5,
                                               format="%.1f", key="dec_fallback") / 100
                meses_fallback = st.number_input("Duração máxima (meses)", 6, 600, 24,
                                                  key="meses_fallback")
                st.session_state["fallback_curva"] = persistencia_padrao(
                    n_meses=int(meses_fallback), decaimento_mensal=dec_fallback
                )
            else:
                st.session_state["fallback_curva"] = None

            st.markdown("---")
            st.markdown("**🕐 Horizonte máximo de projeção**")
            _max_meses_default = st.session_state.get("max_meses_total", 120)
            _max_meses_input = st.number_input(
                "Máximo de meses a projetar (por coorte)",
                min_value=12, max_value=600, value=int(_max_meses_default), step=12,
                help="Teto máximo de meses projetados por coorte de NB ou Stock, contando renovações. "
                     "A curva de persistência encerra a projeção antes desse limite se cancelar tudo. "
                     "Padrão: 120 meses.",
                key="max_meses_input",
            )
            if _max_meses_input != st.session_state.get("max_meses_total"):
                st.session_state["max_meses_total"] = int(_max_meses_input)

        # Painel de produtos sem curva de persistência
        st.markdown("---")
        _produtos_carregados = _get_produtos_carregados()
        if _produtos_carregados:
            _curvas = st.session_state.get("curvas_persistencia", {})
            _produtos_com_curva = {str(p) for p in _curvas.keys()}
            _sem_curva = sorted(_produtos_carregados - _produtos_com_curva)
            _fallback_persist_ativo = st.session_state.get("fallback_curva") is not None
            if _sem_curva:
                _sfx = " — **curva padrão (fallback) será aplicada.**" if _fallback_persist_ativo \
                       else " — esses produtos serão excluídos da projeção (ative o fallback)."
                st.warning(
                    f"⚠️ **{len(_sem_curva)} produto(s) sem curva de persistência:** "
                    f"`{', '.join(_sem_curva)}`{_sfx}"
                )
            else:
                st.success("✅ Todos os produtos têm curva de persistência cadastrada.")

        # ── Persistência Savings ────────────────────────
        st.markdown("---")
        st.subheader("📉 Curvas de Persistência — Savings")
        st.info(
            "Para Savings, a persistência reduz o `montante_capital` e `quantidade_certificados` "
            "conforme os clientes saem. Carregue um Excel separado ou use o fallback abaixo."
        )
        curvas_sav = st.session_state.get("curvas_persistencia_savings", {})
        if curvas_sav:
            st.success(f"✅ Curvas Savings carregadas para {len(curvas_sav)} produto(s): {list(curvas_sav.keys())}")

        col_sp1, col_sp2 = st.columns([2, 1])
        with col_sp1:
            persist_sav_file = st.file_uploader(
                "Excel de Persistência Savings (.xlsx)",
                type=["xlsx"], key="persist_sav_upload",
            )
            if persist_sav_file:
                try:
                    curvas_sav = carregar_persistencia_excel(persist_sav_file)
                    st.session_state["curvas_persistencia_savings"] = curvas_sav
                    st.success(f"✅ {persist_sav_file.name} carregado — {len(curvas_sav)} produto(s)")
                except Exception as e:
                    st.error(f"Erro: {e}")
            if curvas_sav:
                prod_prev_sav = st.selectbox("Visualizar curva Savings", list(curvas_sav.keys()), key="preview_prod_sav")
                if prod_prev_sav:
                    import plotly.express as px
                    cv = curvas_sav[prod_prev_sav]
                    df_cv = pd.DataFrame({"Mês de Vida": list(cv.keys()), "Persistência (%)": [v*100 for v in cv.values()]})
                    fig_sv = px.line(df_cv, x="Mês de Vida", y="Persistência (%)",
                                     title=f"Curva Savings — Produto {prod_prev_sav}", markers=True)
                    fig_sv.add_hline(y=0, line_dash="dash", line_color="red")
                    st.plotly_chart(fig_sv, width="stretch")
        with col_sp2:
            st.markdown("**⚙️ Fallback Savings**")
            usar_fallback_sav = st.checkbox("Usar curva padrão (Savings)", value=True, key="persist_sav_fallback")
            if usar_fallback_sav:
                dec_sav = st.number_input("Decaimento mensal (%)", 0.0, 10.0, 4.0, 0.5,
                                           format="%.1f", key="dec_fallback_sav") / 100
                meses_sav = st.number_input("Duração máxima (meses)", 6, 600, 25, key="meses_fallback_sav")
                st.session_state["fallback_curva_savings"] = persistencia_padrao(
                    n_meses=int(meses_sav), decaimento_mensal=dec_sav
                )
            else:
                st.session_state["fallback_curva_savings"] = None
            st.markdown("---")
            st.markdown("**🕐 Horizonte máximo Savings**")
            _max_sav = st.session_state.get("max_meses_savings", 120)
            _max_sav_in = st.number_input(
                "Máximo de meses (Savings)", min_value=12, max_value=600,
                value=int(_max_sav), step=12, key="max_meses_sav_input",
            )
            if _max_sav_in != st.session_state.get("max_meses_savings"):
                st.session_state["max_meses_savings"] = int(_max_sav_in)

    # ── Sub-tab 5: Hipóteses Savings ────────────────────
    with sub5:
        st.subheader("💰 Hipóteses Savings — TAF, Aporte e Carregamento")
        st.info(
            "Define os parâmetros financeiros dos produtos de previdência/capitalização:\n\n"
            "- **taf_anual_pct**: Taxa de Administração anual sobre o capital (ex: 0.0020 = 0,20% a.a.)\n"
            "- **aporte_medio**: Contribuição mensal média por certificado (R$)\n"
            "- **carregamento_por_aporte**: Valor fixo por aporte retido como receita (= prêmio de risco)\n\n"
            "Carregado automaticamente de `savings_hipoteses.csv` na pasta de inputs."
        )
        sav_file_up = st.file_uploader("Substituir savings_hipoteses.csv", type=["csv"], key="sav_hip_upload")
        if sav_file_up:
            df_sav_up = pd.read_csv(sav_file_up, sep=";", decimal=",")
            st.session_state["savings_hipoteses_manual"] = df_sav_up
            st.success(f"✅ {sav_file_up.name} carregado")
        default_sav_hip = st.session_state.get("savings_hipoteses_manual", pd.DataFrame({
            "produto_atuarial": [4001],
            "businessline": ["Savings"],
            "taf_anual_pct": [0.0020],
            "aporte_medio": [100.0],
            "carregamento_por_aporte": [10.0],
        }))
        if not isinstance(default_sav_hip, pd.DataFrame):
            default_sav_hip = pd.DataFrame(default_sav_hip)
        edited_sav = st.data_editor(default_sav_hip, num_rows="dynamic", width="stretch", key="sav_hip_editor")
        st.session_state["savings_hipoteses_manual"] = edited_sav
        _auto_salvar_csv(edited_sav, "savings_hipoteses.csv", "_hash_sav_hip")


# ═══════════════════════════════════════════════════════
# TAB 3 — VARIÁVEIS CUSTOM
# ═══════════════════════════════════════════════════════
with tab3:
    st.header("🔧 Variáveis Custom")
    st.info("Crie variáveis novas montando nós conectados ou escrevendo uma fórmula livre.")

    modo_criacao = st.radio(
        "Modo de criação",
        ["🧩 Node Builder", "✏️ Fórmula Livre"],
        horizontal=True
    )

    if modo_criacao == "✏️ Fórmula Livre":
        st.subheader("✏️ Nova Variável via Fórmula")
        col_a, col_b = st.columns(2)
        with col_a:
            nome_var = st.text_input("Nome da variável", placeholder="ex: reserva_tecnica")
            sinal_npbt = st.selectbox("Impacto no NPBT", ["negativo (-)", "positivo (+)"])
            afeta_npbt = st.checkbox("Afeta o NPBT?", value=True)
        with col_b:
            st.markdown("**Variáveis disponíveis:**")
            for v in VARIAVEIS_DISPONIVEIS:
                st.code(v, language=None)

        formula = st.text_area("Fórmula (expressão Python)",
                               placeholder="ex: premio_ganho_calculado * 0.03", height=100)

        if st.button("➕ Adicionar Variável", key="add_formula"):
            if nome_var and formula:
                grafo = [
                    {"id": f"formula_{nome_var}", "tipo": "formula_livre",
                     "parametros": {"formula": formula}},
                    {"id": f"saida_{nome_var}", "tipo": "saida_variavel",
                     "parametros": {"nome_variavel": nome_var,
                                    "sinal": "negativo" if "negativo" in sinal_npbt else "positivo",
                                    "afeta_npbt": afeta_npbt},
                     "entradas": [{"id": f"formula_{nome_var}", "tipo": "formula_livre",
                                   "parametros": {"formula": formula}}]}
                ]
                st.session_state["nos_custom"].append(grafo)
                st.session_state["variaveis_criadas"].append(nome_var)
                st.success(f"✅ Variável '{nome_var}' adicionada!")
            else:
                st.warning("Preencha nome e fórmula.")

    else:
        st.subheader("🧩 Node Builder")
        col_n1, col_n2, col_n3 = st.columns(3)

        with col_n1:
            st.markdown("**① Entrada**")
            tipo_entrada = st.selectbox("Tipo de entrada", ["input_coluna", "constante"])
            if tipo_entrada == "input_coluna":
                coluna_entrada = st.selectbox("Coluna", VARIAVEIS_DISPONIVEIS)
                no_entrada = {"id": "entrada", "tipo": "input_coluna",
                              "parametros": {"coluna": coluna_entrada}}
            else:
                val_constante = st.number_input("Valor", value=0.0, format="%.6f")
                no_entrada = {"id": "entrada", "tipo": "constante",
                              "parametros": {"valor": val_constante}}

        with col_n2:
            st.markdown("**② Operação**")
            tipo_op = st.selectbox("Operação", ["percentual", "operacao", "condicional", "nenhuma"])
            no_op = None
            if tipo_op == "percentual":
                pct = st.number_input("Percentual", 0.0, 10.0, 0.05, 0.01, format="%.4f")
                no_op = {"id": "operacao", "tipo": "percentual",
                         "parametros": {"percentual": pct}, "entradas": [no_entrada]}
            elif tipo_op == "operacao":
                op = st.selectbox("Operador", ["soma", "subtracao", "multiplicacao", "divisao"])
                col2_entrada = st.selectbox("Segunda coluna", VARIAVEIS_DISPONIVEIS, key="col2")
                no_entrada2 = {"id": "entrada2", "tipo": "input_coluna",
                               "parametros": {"coluna": col2_entrada}}
                no_op = {"id": "operacao", "tipo": "operacao",
                         "parametros": {"operador": op},
                         "entradas": [no_entrada, no_entrada2]}
            elif tipo_op == "condicional":
                col_cond = st.selectbox("Coluna condição",
                                        VARIAVEIS_DISPONIVEIS + ["tipo_premio"])
                val_cond = st.text_input("Valor da condição", "PM")
                val_true = st.number_input("Se verdadeiro", value=1.0, format="%.4f")
                val_false = st.number_input("Se falso", value=0.0, format="%.4f")
                no_op = {"id": "operacao", "tipo": "condicional",
                         "parametros": {"coluna_condicao": col_cond,
                                        "valor_condicao": val_cond,
                                        "valor_verdadeiro": val_true,
                                        "valor_falso": val_false}}

        with col_n3:
            st.markdown("**③ Saída**")
            nome_var_no = st.text_input("Nome da variável", placeholder="ex: taxa_retencao",
                                         key="nome_var_no")
            sinal_no = st.selectbox("Impacto no NPBT",
                                     ["negativo (-)", "positivo (+)"], key="sinal_no")
            afeta_npbt_no = st.checkbox("Afeta o NPBT?", value=True, key="afeta_npbt_no")

        if st.button("➕ Criar Variável com Nós", key="add_no"):
            if nome_var_no:
                no_final = no_op if no_op else no_entrada
                no_saida = {
                    "id": f"saida_{nome_var_no}", "tipo": "saida_variavel",
                    "parametros": {
                        "nome_variavel": nome_var_no,
                        "sinal": "negativo" if "negativo" in sinal_no else "positivo",
                        "afeta_npbt": afeta_npbt_no
                    },
                    "entradas": [no_final]
                }
                grafo = [no_entrada]
                if no_op:
                    grafo.append(no_op)
                grafo.append(no_saida)
                st.session_state["nos_custom"].append(grafo)
                st.session_state["variaveis_criadas"].append(nome_var_no)
                st.success(f"✅ Variável '{nome_var_no}' criada!")
            else:
                st.warning("Defina o nome da variável.")

    if st.session_state["variaveis_criadas"]:
        st.markdown("---")
        st.subheader("📋 Variáveis Criadas")
        for i, nome in enumerate(st.session_state["variaveis_criadas"]):
            col_v1, col_v2 = st.columns([4, 1])
            with col_v1:
                st.markdown(f"**{i+1}.** `{nome}`")
            with col_v2:
                if st.button("🗑️", key=f"del_var_{i}"):
                    st.session_state["nos_custom"].pop(i)
                    st.session_state["variaveis_criadas"].pop(i)
                    st.rerun()

        st.markdown("---")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Exportar configuração JSON"):
                config_json = json.dumps(st.session_state["nos_custom"],
                                         ensure_ascii=False, indent=2)
                st.download_button("⬇️ Download JSON", config_json,
                                   "variaveis_custom.json", "application/json")
        with col_s2:
            json_upload = st.file_uploader("📂 Carregar configuração JSON", type=["json"])
            if json_upload:
                config = json.load(json_upload)
                st.session_state["nos_custom"] = config
                st.session_state["variaveis_criadas"] = [
                    g[-1]["parametros"]["nome_variavel"]
                    for g in config if g and g[-1]["tipo"] == "saida_variavel"
                ]
                st.success("Configuração carregada!")


# ═══════════════════════════════════════════════════════
# TAB 4 — EXECUTAR
# ═══════════════════════════════════════════════════════
with tab4:
    st.header("▶️ Executar Engine")

    col_ex1, col_ex2, col_ex3 = st.columns(3)
    with col_ex1:
        incluir_stock = st.checkbox("Incluir Stock", value=True)
        incluir_nb    = st.checkbox("Incluir New Business", value=True)
    with col_ex2:
        _cat_opcoes = ["Protection + Savings", "Somente Protection", "Somente Savings"]
        _cat_sel = st.selectbox("Categoria", _cat_opcoes, key="exec_categoria_sel")
        incluir_protection = _cat_sel in ("Protection + Savings", "Somente Protection")
        incluir_savings    = _cat_sel in ("Protection + Savings", "Somente Savings")
    with col_ex3:
        nome_output = st.text_input("Nome do arquivo output", "budget_output.csv")

    st.markdown("---")

    # ── Pipeline em 2 blocos ──────────────────────────────
    st.markdown("##### O que recalcular?")
    _col_blk1, _col_blk2 = st.columns(2)
    with _col_blk1:
        _rodar_proj = st.checkbox(
            "🔵 Bloco 1 — Projeções",
            value=True,
            help="Expansão mês a mês, persistência, TAF/Carregamento Savings. "
                 "Obrigatório se ainda não houver projeção salva."
        )
    with _col_blk2:
        _rodar_hip = st.checkbox(
            "🟠 Bloco 2 — Hipóteses",
            value=True,
            help="Sinistros, Comissão, Gastos, Variáveis Custom e consolidação do resultado. "
                 "Pode ser rodado isoladamente se o Bloco 1 já estiver calculado."
        )

    _tem_proj_salva = st.session_state.get("df_projecao") is not None
    if not _rodar_proj and not _tem_proj_salva:
        st.warning("⚠️ Nenhuma projeção salva. Marque **Bloco 1** para gerar.")
    elif not _rodar_proj and _tem_proj_salva:
        st.info("🔵 Bloco 1 será pulado — usando projeção já calculada.")
    if st.session_state["df_resultado"] is not None:
        st.info("✅ Resultado anterior disponível. Clique em **Re-executar** para recalcular.")

    st.markdown("---")

    _label_btn = "🔄 Re-executar" if st.session_state["df_resultado"] is not None else "🚀 Executar Cálculo"
    if st.button(_label_btn, type="primary", width="stretch"):
        _progresso = st.progress(0, text="Iniciando...")
        log = []

        try:
            from engine.nb_processor import expandir_nb_mes_a_mes, carregar_new_business
            from engine.stock_processor import expandir_stock_mes_a_mes, carregar_stock

            horizonte      = st.session_state.get("horizonte_por_produto", {"default": 12})
            _max_meses     = int(st.session_state.get("max_meses_total", 120))
            _max_meses_sav = int(st.session_state.get("max_meses_savings", 120))
            _pasta_exec    = st.session_state.get("pasta_fonte", "")

            # ── Sempre recarrega hipóteses do disco antes de executar ──
            _progresso.progress(2, text="Recarregando inputs do disco...")
            if _pasta_exec:
                for _arq, _tipo in [
                    ("sinistros.csv",        "sin_manual"),
                    ("comissao.csv",         "com_manual"),
                    ("gastos.csv",           "gas_manual"),
                    ("savings_hipoteses.csv","savings_hipoteses_manual_raw"),
                ]:
                    _p = Path(_pasta_exec) / _arq
                    if _p.exists():
                        try:
                            if _tipo == "savings_hipoteses_manual_raw":
                                st.session_state["savings_hipoteses_manual"] = carregar_hipoteses_savings(str(_p))
                            elif _tipo == "sin_manual":
                                st.session_state[_tipo] = pd.read_csv(_p, sep=";", decimal=",")
                            elif _tipo == "com_manual":
                                st.session_state[_tipo] = pd.read_csv(_p, sep=";", decimal=",")
                            elif _tipo == "gas_manual":
                                st.session_state[_tipo] = pd.read_csv(_p, sep=";", decimal=",")
                        except Exception:
                            pass
                _pers_path = Path(_pasta_exec) / "persistencia.xlsx"
                if _pers_path.exists():
                    try:
                        st.session_state["curvas_persistencia"] = carregar_persistencia_excel(str(_pers_path))
                    except Exception:
                        pass

            # Savings params
            _hip_sav_df = st.session_state.get("savings_hipoteses_manual")
            if _hip_sav_df is None and _pasta_exec:
                _sav_path = Path(_pasta_exec) / "savings_hipoteses.csv"
                if _sav_path.exists():
                    _hip_sav_df = carregar_hipoteses_savings(str(_sav_path))
                    st.session_state["savings_hipoteses_manual"] = _hip_sav_df
            _sav_params = savings_params_dict(_hip_sav_df) if _hip_sav_df is not None and not _hip_sav_df.empty else {}

            def _filtrar_categoria(df_in):
                if "categoria" not in df_in.columns:
                    return df_in if incluir_protection else pd.DataFrame()
                mask_prot = df_in["categoria"] != "Savings"
                mask_sav  = df_in["categoria"] == "Savings"
                parts = []
                if incluir_protection:
                    parts.append(df_in[mask_prot])
                if incluir_savings:
                    parts.append(df_in[mask_sav])
                return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

            def _ler_csv_input(nome_arquivo, bytes_key):
                """Lê do disco (sempre mais recente) ou cai no cache de bytes."""
                if _pasta_exec and (Path(_pasta_exec) / nome_arquivo).exists():
                    return pd.read_csv(Path(_pasta_exec) / nome_arquivo, sep=";", decimal=",")
                if bytes_key in st.session_state:
                    return pd.read_csv(BytesIO(st.session_state[bytes_key]), sep=";", decimal=",")
                return None

            def _preparar_df(df):
                if df is None:
                    return None
                df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
                for col in ["data_fim_mes", "data_ini_mes", "data_inicio_vigencia", "data_fim_vigencia"]:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
                # tipo_premio NaN em Savings → "savings"
                if "categoria" in df.columns and "tipo_premio" in df.columns:
                    df["tipo_premio"] = df["tipo_premio"].astype(str).str.strip()
                    _mask_sav_nan = (df["categoria"] == "Savings") & df["tipo_premio"].isin(["nan","NaN","","None"])
                    df.loc[_mask_sav_nan, "tipo_premio"] = "savings"
                return df

            # ════════════════════════════════════════════════
            # BLOCO 1 — Projeções
            # ════════════════════════════════════════════════
            if _rodar_proj:
                _progresso.progress(5, text="Bloco 1 — Expansão Stock...")
                frames = []

                # 1. Stock
                if incluir_stock:
                    _df_stock_raw = _preparar_df(_ler_csv_input("stock.csv", "stock_bytes_loaded"))
                    if _df_stock_raw is not None:
                        # Validação: tipo_premio NaN em Protection
                        if "categoria" in _df_stock_raw.columns and "tipo_premio" in _df_stock_raw.columns:
                            _nan_prot = (
                                (_df_stock_raw["categoria"] != "Savings") &
                                _df_stock_raw["tipo_premio"].isin(["nan","NaN","","None"])
                            ).sum()
                            if _nan_prot > 0:
                                st.warning(f"⚠️ Stock: {_nan_prot} linha(s) de Protection com tipo_premio nulo — serão tratadas como PM.")
                        _df_stock_raw = _filtrar_categoria(_df_stock_raw)
                    if _df_stock_raw is not None and not _df_stock_raw.empty:
                        df_stock_exp = expandir_stock_mes_a_mes(
                            _df_stock_raw, horizonte, mes_base,
                            max_meses_total=_max_meses,
                            savings_params=_sav_params,
                            max_meses_savings=_max_meses_sav,
                        )
                        frames.append(df_stock_exp)
                        log.append(f"✅ Stock: {len(df_stock_exp):,} registros expandidos")
                    else:
                        log.append("⚠️ Stock: nenhum dado encontrado — ignorado")

                _progresso.progress(25, text="Bloco 1 — Expansão New Business...")

                # 2. New Business
                if incluir_nb:
                    _df_nb_raw = _preparar_df(_ler_csv_input("new_business.csv", "nb_bytes_loaded"))
                    if _df_nb_raw is not None:
                        if "categoria" in _df_nb_raw.columns and "tipo_premio" in _df_nb_raw.columns:
                            _nan_prot_nb = (
                                (_df_nb_raw["categoria"] != "Savings") &
                                _df_nb_raw["tipo_premio"].isin(["nan","NaN","","None"])
                            ).sum()
                            if _nan_prot_nb > 0:
                                st.warning(f"⚠️ NB: {_nan_prot_nb} linha(s) de Protection com tipo_premio nulo — serão tratadas como PM.")
                        _df_nb_raw = _filtrar_categoria(_df_nb_raw)
                    if _df_nb_raw is not None and not _df_nb_raw.empty:
                        from engine.nb_processor import expandir_nb_mes_a_mes as _expandir_nb
                        df_nb_exp = _expandir_nb(
                            _df_nb_raw, horizonte,
                            max_meses_total=_max_meses,
                            savings_params=_sav_params,
                            max_meses_savings=_max_meses_sav,
                        )
                        frames.append(df_nb_exp)
                        log.append(f"✅ New Business: {len(df_nb_exp):,} registros expandidos")
                    else:
                        log.append("⚠️ New Business: nenhum dado encontrado — ignorado")

                if not frames:
                    st.warning("⚠️ Nenhum dado de Stock ou NB disponível. Verifique os inputs.")
                    _progresso.progress(100, text="Concluído (sem dados)")
                    st.stop()

                df_total = pd.concat(frames, ignore_index=True)
                _progresso.progress(40, text="Bloco 1 — Aplicando Persistência...")

                # 3. Persistência
                curvas_persist = st.session_state.get("curvas_persistencia", {})
                fallback       = st.session_state.get("fallback_curva", None)
                curvas_sav_p   = st.session_state.get("curvas_persistencia_savings", {})
                fallback_sav   = st.session_state.get("fallback_curva_savings", None)

                if "categoria" in df_total.columns:
                    mask_prot_p = df_total["categoria"] != "Savings"
                    mask_sav_p  = df_total["categoria"] == "Savings"
                    partes_persist = []
                    if incluir_protection and mask_prot_p.any():
                        if curvas_persist or fallback:
                            antes_p = mask_prot_p.sum()
                            _dp = aplicar_persistencia_acumulada(
                                df_total[mask_prot_p].copy(), curvas=curvas_persist, fallback_curva=fallback)
                            partes_persist.append(_dp)
                            log.append(f"✅ Persistência Protection — {antes_p - len(_dp):,} linhas canceladas")
                        else:
                            partes_persist.append(df_total[mask_prot_p].copy())
                            log.append("⚠️ Persistência Protection não configurada")
                    if incluir_savings and mask_sav_p.any():
                        if curvas_sav_p or fallback_sav:
                            antes_s = mask_sav_p.sum()
                            _ds = aplicar_persistencia_acumulada(
                                df_total[mask_sav_p].copy(), curvas=curvas_sav_p, fallback_curva=fallback_sav)
                            partes_persist.append(_ds)
                            log.append(f"✅ Persistência Savings — {antes_s - len(_ds):,} linhas canceladas")
                        else:
                            partes_persist.append(df_total[mask_sav_p].copy())
                            log.append("⚠️ Persistência Savings não configurada")
                    df_total = pd.concat(partes_persist, ignore_index=True) if partes_persist else df_total
                else:
                    if curvas_persist or fallback:
                        antes = len(df_total)
                        df_total = aplicar_persistencia_acumulada(
                            df_total, curvas=curvas_persist, fallback_curva=fallback)
                        log.append(f"✅ Persistência aplicada — {antes - len(df_total):,} canceladas")
                    else:
                        log.append("⚠️ Persistência não configurada")

                _progresso.progress(55, text="Bloco 1 — TAF e Carregamento Savings...")

                # 4. Savings — TAF e Carregamento (pós-persistência)
                if incluir_savings and _hip_sav_df is not None and not _hip_sav_df.empty:
                    df_total = aplicar_savings(df_total, _hip_sav_df)
                    log.append("✅ TAF e Carregamento Savings calculados")

                # Salva projeção (Bloco 1)
                st.session_state["df_projecao"] = df_total.copy()
                log.append(f"💾 Projeção salva ({len(df_total):,} linhas)")

            else:
                # Bloco 1 pulado — usa df_projecao existente
                df_total = st.session_state["df_projecao"].copy()
                log.append(f"🔵 Bloco 1 pulado — usando projeção existente ({len(df_total):,} linhas)")

            # Salva snapshot para auditoria
            st.session_state["df_auditoria"] = df_total.copy()

            # ════════════════════════════════════════════════
            # BLOCO 2 — Hipóteses
            # ════════════════════════════════════════════════
            if _rodar_hip:
                _progresso.progress(60, text="Bloco 2 — Sinistros...")

                # 5. Sinistros
                hip_sin = st.session_state.get("sin_manual",
                    pd.DataFrame(columns=["produto_atuarial","businessline","tipo_hipotese","valor","frequencia","severidade_media"]))
                if not isinstance(hip_sin, pd.DataFrame):
                    hip_sin = pd.DataFrame(hip_sin)
                if incluir_protection and "categoria" in df_total.columns:
                    mask_p = df_total["categoria"] != "Savings"
                    if mask_p.any():
                        _dp = aplicar_sinistros(df_total[mask_p].copy(), hip_sin, fallback=st.session_state.get("sin_fallback"))
                        df_total.loc[mask_p, "sinistros_calculado"] = _dp["sinistros_calculado"].values
                if incluir_savings and "categoria" in df_total.columns:
                    mask_s = df_total["categoria"] == "Savings"
                    if mask_s.any():
                        _ds = aplicar_sinistros(df_total[mask_s].copy(), hip_sin, fallback=st.session_state.get("sin_fallback_savings"))
                        df_total.loc[mask_s, "sinistros_calculado"] = _ds["sinistros_calculado"].values
                if "sinistros_calculado" not in df_total.columns:
                    df_total = aplicar_sinistros(df_total, hip_sin, fallback=st.session_state.get("sin_fallback"))
                log.append("✅ Sinistros aplicados")

                _progresso.progress(70, text="Bloco 2 — Comissão...")

                # 6. Comissão
                hip_com = st.session_state.get("com_manual",
                    pd.DataFrame(columns=["produto_atuarial","businessline","tipo_regra","valor"]))
                if not isinstance(hip_com, pd.DataFrame):
                    hip_com = pd.DataFrame(hip_com)
                if incluir_protection and "categoria" in df_total.columns:
                    mask_p = df_total["categoria"] != "Savings"
                    if mask_p.any():
                        _dp = aplicar_comissao(df_total[mask_p].copy(), hip_com, fallback=st.session_state.get("com_fallback"))
                        df_total.loc[mask_p, "comissao_calculada"] = _dp["comissao_calculada"].values
                if incluir_savings and "categoria" in df_total.columns:
                    mask_s = df_total["categoria"] == "Savings"
                    if mask_s.any():
                        _ds = aplicar_comissao(df_total[mask_s].copy(), hip_com, fallback=st.session_state.get("com_fallback_savings"))
                        df_total.loc[mask_s, "comissao_calculada"] = _ds["comissao_calculada"].values
                if "comissao_calculada" not in df_total.columns:
                    df_total = aplicar_comissao(df_total, hip_com, fallback=st.session_state.get("com_fallback"))
                log.append("✅ Comissão aplicada")

                _progresso.progress(80, text="Bloco 2 — Gastos e Other NBI...")

                # 7. Gastos
                hip_gas = st.session_state.get("gas_manual",
                    pd.DataFrame(columns=["produto_atuarial","businessline","tipo_gasto","tipo_regra","valor"]))
                if not isinstance(hip_gas, pd.DataFrame):
                    hip_gas = pd.DataFrame(hip_gas)
                if incluir_protection and "categoria" in df_total.columns:
                    mask_p = df_total["categoria"] != "Savings"
                    if mask_p.any():
                        _dp = df_total[mask_p].copy()
                        _dp = aplicar_gastos(_dp, hip_gas, "gastos",    fallback=st.session_state.get("gas_gastos_fallback"))
                        _dp = aplicar_gastos(_dp, hip_gas, "other_nbi", fallback=st.session_state.get("gas_othernbi_fallback"))
                        for _gc in ["gastos_calculado", "other_nbi_calculado"]:
                            if _gc in _dp.columns:
                                df_total.loc[mask_p, _gc] = _dp[_gc].values
                if incluir_savings and "categoria" in df_total.columns:
                    mask_s = df_total["categoria"] == "Savings"
                    if mask_s.any():
                        _ds = df_total[mask_s].copy()
                        _ds = aplicar_gastos(_ds, hip_gas, "gastos",    fallback=st.session_state.get("gas_gastos_fallback_sav"))
                        _ds = aplicar_gastos(_ds, hip_gas, "other_nbi", fallback=st.session_state.get("gas_othernbi_fallback_sav"))
                        for _gc in ["gastos_calculado", "other_nbi_calculado"]:
                            if _gc in _ds.columns:
                                df_total.loc[mask_s, _gc] = _ds[_gc].values
                if "gastos_calculado" not in df_total.columns:
                    df_total = aplicar_gastos(df_total, hip_gas, "gastos",    fallback=st.session_state.get("gas_gastos_fallback"))
                    df_total = aplicar_gastos(df_total, hip_gas, "other_nbi", fallback=st.session_state.get("gas_othernbi_fallback"))
                log.append("✅ Gastos e Other NBI aplicados")

                _progresso.progress(90, text="Bloco 2 — Consolidando resultado...")

                # 8. Consolidação
                visoes = ["LOCAL", "IFRS17"] if visao == "Ambas" else [visao]
                frames_resultado = []
                for v in visoes:
                    df_v = consolidar_resultado(
                        df_total, visao=v,
                        taxa_desconto_ifrs=taxa_desconto if visao != "LOCAL" else 0.0,
                        percentual_ra=percentual_ra if visao != "LOCAL" else 0.05,
                        usar_paa=usar_paa,
                        variaveis_custom=st.session_state["nos_custom"] or None
                    )
                    frames_resultado.append(df_v)

                df_final = pd.concat(frames_resultado, ignore_index=True)
                st.session_state["df_resultado"] = df_final
                log.append(f"✅ Resultado calculado: {len(df_final):,} linhas")

                # Reset filtros
                for _fk in ["filtro_visao_res", "filtro_produto_res", "filtro_bl_res",
                             "filtro_fonte", "filtro_tipo_premio", "filtro_movimento",
                             "filtro_categoria_res"]:
                    st.session_state.pop(_fk, None)

                # Auto-salva
                _vid = (st.session_state.get("sessao_carregada") or {}).get("id")
                if _vid:
                    try:
                        salvar_resultado_na_versao(
                            _vid, df_final, st.session_state.get("df_auditoria"),
                            fallbacks=_coletar_fallbacks_estado(),
                            df_fallback_curva=st.session_state.get("fallback_curva"),
                            df_fallback_curva_sav=st.session_state.get("fallback_curva_savings"),
                        )
                        log.append("💾 Resultado salvo na sessão automaticamente.")
                    except Exception as _e:
                        log.append(f"⚠️ Não foi possível salvar o resultado na sessão: {_e}")

                csv_bytes = df_final.to_csv(sep=";", decimal=",",
                                             index=False, encoding="utf-8-sig").encode("utf-8-sig")

            _progresso.progress(100, text="✅ Concluído!")
            for msg in log:
                st.success(msg)

            if st.session_state.get("df_resultado") is not None:
                st.download_button("⬇️ Baixar Output CSV", csv_bytes if _rodar_hip else b"",
                                   nome_output, "text/csv", width="stretch")

        except Exception as e:
            _progresso.progress(100, text="❌ Erro")
            st.error(f"Erro durante execução: {e}")
            import traceback
            st.code(traceback.format_exc())


# ═══════════════════════════════════════════════════════
# TAB 5 — RESULTADO
# ═══════════════════════════════════════════════════════
with tab5:
    st.header("📊 Resultado")

    if st.session_state["df_resultado"] is None:
        st.info("Execute o cálculo na aba '▶️ Executar' para ver os resultados.")
    else:
        df_res = st.session_state["df_resultado"].copy()

        # ── Alerta de sobreposição Stock (mes_base) × NB (menor safra_venda) ──
        if "nb_bytes_loaded" in st.session_state:
            try:
                _nb_chk = pd.read_csv(BytesIO(st.session_state["nb_bytes_loaded"]),
                                      sep=";", decimal=",", dtype=str)
                _nb_chk.columns = [c.strip().lower() for c in _nb_chk.columns]
                _col_n = next((c for c in ["safra_venda", "data_ini_mes",
                                            "data_inicio_vigencia"] if c in _nb_chk.columns), None)
                _dt_mb = pd.to_datetime(
                    st.session_state.get("mes_base_config", str(date.today().replace(day=1))),
                    errors="coerce"
                )
                if _col_n and pd.notna(_dt_mb):
                    _min_n = pd.to_datetime(_nb_chk[_col_n], format="mixed", dayfirst=True, errors="coerce").min()
                    if pd.notna(_min_n) and _min_n <= _dt_mb:
                        st.warning(
                            f"⚠️ **Atenção — sobreposição Stock × New Business!** "
                            f"A menor `safra_venda` do NB é **{_min_n.strftime('%b/%Y')}**, "
                            f"mas o Mês Base do Stock é **{_dt_mb.strftime('%b/%Y')}**. "
                            f"Verifique o Data Quality antes de usar estes resultados."
                        )
            except Exception:
                pass

        # ── Alerta de duplicidade no resultado ──
        _CHAVES_RES = ["safra", "produto_atuarial", "businessline", "safra_venda",
                       "tipo_premio", "data_inicio_vigencia", "data_fim_vigencia",
                       "mes_projecao", "fonte"]
        _chaves_res_presentes = [c for c in _CHAVES_RES if c in df_res.columns]
        if len(_chaves_res_presentes) >= 4:
            _dups_res = df_res[df_res.duplicated(subset=_chaves_res_presentes, keep=False)]
            if not _dups_res.empty:
                _n_dup_res = _dups_res.groupby(_chaves_res_presentes).ngroups
                with st.expander(
                    f"⚠️ **Possível duplicidade no resultado — {_n_dup_res} combinação(ões) de chaves aparecem mais de uma vez.** "
                    f"Clique para ver os registros.",
                    expanded=False
                ):
                    st.caption(
                        "Linhas com mesma combinação de chaves foram encontradas. "
                        "Se os valores (prêmio, certificados etc.) forem diferentes entre elas, "
                        "os totais estão sendo somados em duplicidade. "
                        "Corrija nos inputs agrupando tudo em uma única linha por chave."
                    )
                    _cols_exibir = _chaves_res_presentes + [
                        c for c in ["valor_premio_emitido", "premio_ganho_calculado",
                                    "quantidade_certificados", "npbt_local"]
                        if c in _dups_res.columns
                    ]
                    st.dataframe(
                        _dups_res[_cols_exibir].sort_values(_chaves_res_presentes).head(200),
                        width="stretch", hide_index=True
                    )

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            if "visao" in df_res.columns:
                visao_filtro = st.multiselect("Visão", df_res["visao"].unique().tolist(),
                                               default=df_res["visao"].unique().tolist(),
                                               key="filtro_visao_res")
                df_res = df_res[df_res["visao"].isin(visao_filtro)]
        with col_f2:
            if "produto_atuarial" in df_res.columns:
                prods = sorted(df_res["produto_atuarial"].unique().tolist())
                prod_filtro = st.multiselect("Produto", prods, default=prods,
                                             key="filtro_produto_res")
                df_res = df_res[df_res["produto_atuarial"].isin(prod_filtro)]
        with col_f3:
            if "businessline" in df_res.columns:
                bls = sorted(df_res["businessline"].dropna().unique().tolist())
                bl_filtro = st.multiselect("Business Line", bls, default=bls,
                                           key="filtro_bl_res")
                df_res = df_res[df_res["businessline"].isin(bl_filtro)]

        col_f4, col_f5, col_f6 = st.columns(3)
        with col_f4:
            if "fonte" in df_res.columns:
                fontes = sorted(df_res["fonte"].dropna().unique().tolist())
                fonte_filtro = st.multiselect("Fonte (Stock / NB)", fontes, default=fontes,
                                              key="filtro_fonte")
                df_res = df_res[df_res["fonte"].isin(fonte_filtro)]
        with col_f5:
            if "tipo_premio" in df_res.columns:
                tipos = sorted(df_res["tipo_premio"].dropna().unique().tolist())
                tipo_filtro = st.multiselect("Tipo de Prêmio", tipos, default=tipos,
                                             key="filtro_tipo_premio")
                if tipos:  # só filtra quando há opções; NaN (Savings) sempre passa
                    df_res = df_res[df_res["tipo_premio"].isin(tipo_filtro) | df_res["tipo_premio"].isna()]
        with col_f6:
            if "movimento" in df_res.columns:
                movs = sorted(df_res["movimento"].dropna().unique().tolist())
                mov_filtro = st.multiselect("Movimento", movs, default=movs,
                                            key="filtro_movimento")
                if movs:  # só filtra quando há opções; NaN sempre passa
                    df_res = df_res[df_res["movimento"].isin(mov_filtro) | df_res["movimento"].isna()]

        col_f7, col_f8, col_f9 = st.columns(3)
        with col_f7:
            if "categoria" in df_res.columns:
                cats = sorted(df_res["categoria"].dropna().unique().tolist())
                cat_filtro = st.multiselect("Categoria", cats, default=cats,
                                            key="filtro_categoria_res")
                df_res = df_res[df_res["categoria"].isin(cat_filtro)]

        st.markdown("---")

        # ── KPI Protection ──────────────────────────────────
        _has_categoria = "categoria" in df_res.columns
        _df_prot_kpi = df_res[df_res["categoria"] != "Savings"] if _has_categoria else df_res
        _df_sav_kpi  = df_res[df_res["categoria"] == "Savings"] if _has_categoria else pd.DataFrame()
        _has_savings  = _has_categoria and not _df_sav_kpi.empty

        if _has_savings:
            st.markdown("**Protection**")
        cols_kpi = st.columns(4)
        kpis_prot = [
            ("Prêmio Ganho", "premio_ganho_calculado", "🏦"),
            ("Sinistros",    "sinistros_calculado",    "⚠️"),
            ("Comissão",     "comissao_calculada",     "💳"),
            ("NPBT Local",   "npbt_local",             "📈"),
        ]
        for i, (label, col, icon) in enumerate(kpis_prot):
            with cols_kpi[i]:
                valor = _df_prot_kpi[col].sum() if col in _df_prot_kpi.columns else 0
                st.metric(f"{icon} {label}", f"{valor:,.0f}")

        # ── KPI Savings ──────────────────────────────────────
        if _has_savings:
            st.markdown("**Savings**")
            cols_kpi_sav = st.columns(4)
            kpis_sav = [
                ("TAF",          "taf_calculado",          "💰"),
                ("Sinistros",    "sinistros_calculado",    "⚠️"),
                ("Carregamento", "carregamento_calculado", "📥"),
                ("NPBT Local",   "npbt_local",             "📈"),
            ]
            for i, (label, col, icon) in enumerate(kpis_sav):
                with cols_kpi_sav[i]:
                    valor = _df_sav_kpi[col].sum() if col in _df_sav_kpi.columns else 0
                    st.metric(f"{icon} {label}", f"{valor:,.0f}")

            # ── KPI Total ────────────────────────────────────
            st.markdown("**Total**")
            cols_kpi_tot = st.columns(4)
            kpis_tot = [
                ("Prêmio + TAF",  ["premio_ganho_calculado", "taf_calculado"],  "🏦"),
                ("Sinistros",     ["sinistros_calculado"],                       "⚠️"),
                ("Comissão + Car",["comissao_calculada", "carregamento_calculado"], "💳"),
                ("NPBT Local",    ["npbt_local"],                                "📈"),
            ]
            for i, (label, cols_list, icon) in enumerate(kpis_tot):
                with cols_kpi_tot[i]:
                    valor = sum(df_res[c].sum() for c in cols_list if c in df_res.columns)
                    st.metric(f"{icon} {label}", f"{valor:,.0f}")

        st.markdown("---")

        if "mes_projecao" in df_res.columns:
            import plotly.express as px

            st.subheader("📅 Resultado por Mês")

            # ── Filtro de movimento ──────────────────────────
            _df_res_graf = df_res.copy()
            if "movimento" in _df_res_graf.columns:
                _movimentos = ["Inicial + Renovação"] + sorted(_df_res_graf["movimento"].dropna().unique().tolist())
                _filtro_mov = st.selectbox("Movimento", _movimentos, key="sel_movimento_mes")
                if _filtro_mov != "Inicial + Renovação":
                    _df_res_graf = _df_res_graf[_df_res_graf["movimento"] == _filtro_mov]

            cols_num = [c for c in [
                "valor_premio_emitido", "premio_ganho_calculado",
                "quantidade_certificados", "montante_capital",
                "sinistros_calculado", "comissao_calculada",
                "taf_calculado", "carregamento_calculado",
                "gastos_calculado", "other_nbi_calculado",
                "npbt_local", "npbt_ifrs17",
            ] if c in _df_res_graf.columns]
            chaves = [c for c in ["mes_projecao", "visao", "categoria"] if c in _df_res_graf.columns]
            df_mes = _df_res_graf.groupby(chaves)[cols_num].sum().reset_index()

            # Adiciona qtd_vendas do NB — filtrado pelos mesmos critérios do resultado
            _nb_bytes = st.session_state.get("nb_bytes_loaded")
            _pasta_nb = st.session_state.get("pasta_fonte", "")
            _nb_path  = Path(_pasta_nb) / "new_business.csv" if _pasta_nb else None
            _nb_src   = None
            if _nb_path and _nb_path.exists():
                _nb_src = str(_nb_path)
            try:
                if _nb_src:
                    _df_nb_v = pd.read_csv(_nb_src, sep=";", decimal=",")
                elif _nb_bytes:
                    _df_nb_v = pd.read_csv(BytesIO(_nb_bytes), sep=";", decimal=",")
                else:
                    _df_nb_v = None
                if _df_nb_v is not None:
                    _df_nb_v.columns = [c.strip().lower().replace(" ", "_") for c in _df_nb_v.columns]
                    # Aplica os mesmos filtros de produto e categoria do resultado
                    if "produto_atuarial" in _df_nb_v.columns and "prod_filtro" in dir():
                        _df_nb_v = _df_nb_v[_df_nb_v["produto_atuarial"].astype(str).isin(
                            [str(p) for p in prod_filtro])]
                    if "categoria" in _df_nb_v.columns and "cat_filtro" in dir():
                        _df_nb_v = _df_nb_v[_df_nb_v["categoria"].isin(cat_filtro)]
                    _col_sv = next((c for c in ["safra_venda", "safra"] if c in _df_nb_v.columns), None)
                    if _col_sv and "quantidade_certificados" in _df_nb_v.columns:
                        _df_nb_v = (_df_nb_v.groupby(_col_sv, dropna=False)["quantidade_certificados"]
                                    .sum().reset_index()
                                    .rename(columns={_col_sv: "mes_projecao",
                                                     "quantidade_certificados": "qtd_vendas"}))
                        df_mes = df_mes.merge(_df_nb_v, on="mes_projecao", how="left")
            except Exception:
                pass

            st.dataframe(df_mes, width="stretch", height=400)

            if "mes_projecao" in df_mes.columns:
                _LABELS = {
                    "qtd_vendas":              "Qtd. Vendas (NB)",
                    "quantidade_certificados": "Qtd. Certificados (projetado)",
                    "montante_capital":        "Montante Capital (Savings)",
                    "valor_premio_emitido":    "Prêmio Emitido",
                    "premio_ganho_calculado":  "Prêmio Ganho",
                    "taf_calculado":           "TAF (Savings)",
                    "carregamento_calculado":  "Carregamento (Savings)",
                    "sinistros_calculado":     "Sinistros",
                    "comissao_calculada":      "Comissão",
                    "gastos_calculado":        "Gastos",
                    "other_nbi_calculado":     "Other NBI",
                    "npbt_local":              "NPBT LOCAL",
                    "npbt_ifrs17":             "NPBT IFRS17",
                }
                _opcoes = {v: k for k, v in _LABELS.items() if k in df_mes.columns}
                if _opcoes:
                    _opcoes_lista = list(_opcoes.keys())
                    _default_idx = _opcoes_lista.index("Prêmio Emitido") if "Prêmio Emitido" in _opcoes_lista else 0
                    _var_label = st.selectbox(
                        "Variável do gráfico",
                        _opcoes_lista,
                        index=_default_idx,
                        key="sel_var_grafico_mes",
                    )
                    _var_col = _opcoes[_var_label]
                    # Cor: categoria se existir e tiver mais de um valor, caso contrário visao
                    _color_col = None
                    if "categoria" in df_mes.columns and df_mes["categoria"].nunique() > 1:
                        _color_col = "categoria"
                    elif "visao" in df_mes.columns:
                        _color_col = "visao"
                    fig = px.line(
                        df_mes, x="mes_projecao", y=_var_col,
                        color=_color_col,
                        title=f"{_var_label} por Mês",
                        labels={"mes_projecao": "Mês", _var_col: _var_label},
                    )
                    st.plotly_chart(fig, width="stretch")

        # ── Demonstrativo Financeiro (P&L) ─────────────────
        st.markdown("---")
        st.subheader("📑 Demonstrativo Financeiro (P&L)")

        def _montar_pl_savings(df_pl):
            """Monta P&L LOCAL para Savings: TAF + Carregamento como receita."""
            _col_data = None
            for _c in ["mes_projecao", "data_fim_mes", "data_ini_mes"]:
                if _c in df_pl.columns:
                    _col_data = _c
                    break
            if _col_data is None:
                return None
            _df = df_pl.copy()
            _df["_ano"] = pd.to_datetime(_df[_col_data], format="mixed", dayfirst=True, errors="coerce").dt.year
            _df = _df.dropna(subset=["_ano"])
            if _df.empty:
                return None
            _df["_ano"] = _df["_ano"].astype(int).astype(str)
            _linhas_sav = [
                ("TAF",              "taf_calculado",          False),
                ("Carregamento",     "carregamento_calculado", False),
                ("(-) Sinistros",    "sinistros_calculado",    True),
                ("(-) Comissão",     "comissao_calculada",     True),
                ("(-) Gastos",       "gastos_calculado",       True),
                ("(-) Other NBI",    "other_nbi_calculado",    True),
                ("═ NPBT Local",     "npbt_local",             False),
            ]
            _anos = sorted(_df["_ano"].unique())
            _rows = []
            for _label, _col, _ in _linhas_sav:
                _vals = _df.groupby("_ano")[_col].sum().to_dict() if _col in _df.columns else {}
                _row = {"": _label}
                _total = 0.0
                for _a in _anos:
                    _v = _vals.get(_a, 0.0)
                    _row[_a] = _v
                    _total += _v
                _row["Total"] = _total
                _rows.append(_row)
            return pd.DataFrame(_rows).set_index("")

        def _montar_pl(df_pl, visao_pl):
            """Monta P&L com linhas = variáveis, colunas = anos + Total."""
            # Aceita mes_projecao (formato AAAA/MM) ou data_fim_mes (datetime/string)
            _col_data = None
            for _c in ["mes_projecao", "data_fim_mes", "data_ini_mes"]:
                if _c in df_pl.columns:
                    _col_data = _c
                    break
            if _col_data is None:
                return None
            _df = df_pl.copy()
            _df["_ano"] = pd.to_datetime(_df[_col_data], format="mixed", dayfirst=True, errors="coerce").dt.year
            _df = _df.dropna(subset=["_ano"])
            if _df.empty:
                return None
            _df["_ano"] = _df["_ano"].astype(int).astype(str)

            if visao_pl == "LOCAL":
                _linhas = [
                    ("Prêmio Ganho",          "premio_ganho_calculado",  False),
                    ("(-) Sinistros",          "sinistros_calculado",     True),
                    ("(-) Comissão",           "comissao_calculada",      True),
                    ("(-) Gastos",             "gastos_calculado",        True),
                    ("(-) Other NBI",          "other_nbi_calculado",     True),
                    ("═ NPBT Local",           "npbt_local",              False),
                ]
            else:
                _linhas = [
                    ("Receita IFRS17",         "ifrs17_revenue",          False),
                    ("(-) Sinistros / LIC",    "sinistros_calculado",     True),
                    ("(-) Comissão",           "comissao_calculada",      True),
                    ("(-) Gastos",             "gastos_calculado",        True),
                    ("(-) Other NBI",          "other_nbi_calculado",     True),
                    ("(+) CSM Amortizado",     "ifrs17_csm_amortizado",   False),
                    ("(-) Risk Adjustment",    "ifrs17_ra",               True),
                    ("═ NPBT IFRS17",          "npbt_ifrs17",             False),
                ]

            _anos = sorted(_df["_ano"].unique())
            _rows = []
            for _label, _col, _negativa in _linhas:
                if _col not in _df.columns:
                    _vals = {a: 0.0 for a in _anos}
                else:
                    _vals = _df.groupby("_ano")[_col].sum().to_dict()
                _row = {"": _label}
                _total = 0.0
                for _a in _anos:
                    _v = _vals.get(_a, 0.0)
                    _row[_a] = _v
                    _total += _v
                _row["Total"] = _total
                _rows.append(_row)

            return pd.DataFrame(_rows).set_index("")

        def _fmt_num(val):
            if isinstance(val, (int, float)) and not pd.isna(val):
                return f"{val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return val if val is not None else ""

        _visoes_res = df_res["visao"].unique().tolist() if "visao" in df_res.columns else ["LOCAL"]

        def _exibir_pl(df_exibir, visao_exibir, titulo):
            _pl = _montar_pl(df_exibir, visao_exibir)
            if _pl is None or _pl.empty:
                return
            st.markdown(f"**{titulo}**")
            _pl_fmt = _pl.copy()
            for _c in _pl_fmt.columns:
                _pl_fmt[_c] = _pl_fmt[_c].apply(_fmt_num)

            def _estilo_pl(row):
                if str(row.name).startswith("═"):
                    return ["font-weight:bold; color:#004F30; background-color:#F0F4F2"] * len(row)
                return [""] * len(row)

            try:
                st.dataframe(_pl_fmt.style.apply(_estilo_pl, axis=1), width="stretch")
            except Exception:
                st.dataframe(_pl_fmt, width="stretch")

        _has_cat_res = "categoria" in df_res.columns
        _has_sav_res = _has_cat_res and (df_res["categoria"] == "Savings").any()

        for _v in _visoes_res:
            st.markdown(f"#### Visão {_v}")
            _df_v = df_res[df_res["visao"] == _v] if "visao" in df_res.columns else df_res

            if _has_sav_res:
                _df_prot_pl = _df_v[_df_v["categoria"] != "Savings"]
                _df_sav_pl  = _df_v[_df_v["categoria"] == "Savings"]
                if not _df_prot_pl.empty:
                    _exibir_pl(_df_prot_pl, _v, "Protection")
                if not _df_sav_pl.empty:
                    # P&L Savings: TAF + Carregamento como receita
                    _df_sav_pl2 = _df_sav_pl.copy()
                    # Cria coluna de receita Savings combinando TAF + Carregamento
                    _df_sav_pl2["_receita_savings"] = (
                        _df_sav_pl2.get("taf_calculado", 0).fillna(0) +
                        _df_sav_pl2.get("carregamento_calculado", 0).fillna(0)
                    )
                    if _v == "LOCAL":
                        _pl_sav = _montar_pl_savings(_df_sav_pl2)
                    else:
                        _pl_sav = _montar_pl(_df_sav_pl2, _v)
                    if _pl_sav is not None and not _pl_sav.empty:
                        st.markdown("**Savings**")
                        _pl_sav_fmt = _pl_sav.copy()
                        for _c in _pl_sav_fmt.columns:
                            _pl_sav_fmt[_c] = _pl_sav_fmt[_c].apply(_fmt_num)
                        def _estilo_pl_sav(row):
                            if str(row.name).startswith("═"):
                                return ["font-weight:bold; color:#004F30; background-color:#F0F4F2"] * len(row)
                            return [""] * len(row)
                        try:
                            st.dataframe(_pl_sav_fmt.style.apply(_estilo_pl_sav, axis=1), width="stretch")
                        except Exception:
                            st.dataframe(_pl_sav_fmt, width="stretch")
                _exibir_pl(_df_v, _v, "Total")
            else:
                _pl = _montar_pl(_df_v, _v)
                if _pl is None or _pl.empty:
                    st.info("Sem dados para montar o P&L.")
                    continue
                _pl_fmt = _pl.copy()
                for _c in _pl_fmt.columns:
                    _pl_fmt[_c] = _pl_fmt[_c].apply(_fmt_num)
                def _estilo_pl(row):
                    if str(row.name).startswith("═"):
                        return ["font-weight:bold; color:#004F30; background-color:#F0F4F2"] * len(row)
                    return [""] * len(row)
                try:
                    st.dataframe(_pl_fmt.style.apply(_estilo_pl, axis=1), width="stretch")
                except Exception:
                    st.dataframe(_pl_fmt, width="stretch")
            st.markdown("")

        st.markdown("---")
        st.subheader("📋 Dados Completos")
        st.dataframe(df_res, width="stretch", height=500)


# ═══════════════════════════════════════════════════════
# TAB AUDITORIA
# ═══════════════════════════════════════════════════════
with tabAudit:
    st.header("🔎 Auditoria dos Números")
    st.caption("Trilha completa por produto: ponto de partida do estoque → decaimento → posição da persistência → valores em cada etapa.")

    if st.session_state["df_auditoria"] is None:
        st.info("Execute o cálculo na aba '▶️ Executar' para ver a auditoria.")
    else:
        df_aud = st.session_state["df_auditoria"].copy()

        # ── Filtros ──────────────────────────────────────────────
        col_f1, col_f2, col_f3 = st.columns(3)
        _filtros = {}

        with col_f1:
            if "produto_atuarial" in df_aud.columns:
                _prods = sorted(df_aud["produto_atuarial"].unique().tolist())
                _sel = st.multiselect("Produto", _prods, default=_prods, key="aud_produto")
                _filtros["produto_atuarial"] = _sel

        with col_f2:
            if "businessline" in df_aud.columns:
                _bls = sorted(df_aud["businessline"].dropna().unique().tolist())
                _sel = st.multiselect("Business Line", _bls, default=_bls, key="aud_bl")
                _filtros["businessline"] = _sel

        with col_f3:
            if "fonte" in df_aud.columns:
                _fontes = sorted(df_aud["fonte"].dropna().unique().tolist())
                _sel = st.multiselect("Fonte", _fontes, default=_fontes, key="aud_fonte")
                _filtros["fonte"] = _sel

        col_f4, col_f5, col_f6 = st.columns(3)

        with col_f4:
            if "tipo_premio" in df_aud.columns:
                _tipos = sorted(df_aud["tipo_premio"].dropna().unique().tolist())
                _sel = st.multiselect("Tipo Prêmio", _tipos, default=_tipos, key="aud_tipo")
                _filtros["tipo_premio"] = _sel

        with col_f5:
            if "safra_venda" in df_aud.columns:
                _safras = sorted(df_aud["safra_venda"].dropna().astype(str).unique().tolist())
                _sel = st.multiselect("Safra Venda", _safras, default=_safras, key="aud_safra")
                _filtros["safra_venda"] = _sel

        with col_f6:
            if "movimento" in df_aud.columns:
                _movs = sorted(df_aud["movimento"].dropna().unique().tolist())
                _sel = st.multiselect("Movimento", _movs, default=_movs, key="aud_mov")
                _filtros["movimento"] = _sel

        col_f7, col_f8, col_f9 = st.columns(3)
        with col_f7:
            if "categoria" in df_aud.columns:
                _cats = sorted(df_aud["categoria"].dropna().unique().tolist())
                _sel = st.multiselect("Categoria", _cats, default=_cats, key="aud_categoria")
                _filtros["categoria"] = _sel

        # Aplica filtros com tratamento de NaN para tipo_premio e movimento (Savings têm NaN nessas colunas)
        for _fcol, _fvals in _filtros.items():
            if not _fvals or _fcol not in df_aud.columns:
                continue
            if _fcol in ("tipo_premio", "movimento"):
                df_aud = df_aud[df_aud[_fcol].isin(_fvals) | df_aud[_fcol].isna()]
            else:
                df_aud = df_aud[df_aud[_fcol].isin(_fvals)]

        st.markdown("---")

        # ── KPIs ─────────────────────────────────────────────────
        _qtd_ini = (
            df_aud[df_aud["mes_vida"] == 0]["quantidade_certificados"].sum()
            if "mes_vida" in df_aud.columns and "quantidade_certificados" in df_aud.columns
            else 0
        )
        _pg  = df_aud["premio_ganho_calculado"].sum() if "premio_ganho_calculado" in df_aud.columns else 0
        _sin = df_aud["sinistros_calculado"].sum()    if "sinistros_calculado"    in df_aud.columns else 0

        # Persistência média em meses = ∑ P(t) por produto, depois média entre produtos
        # Derivado diretamente dos dados de df_aud (responde ao filtro de produto)
        _persist_meses = None
        if "fator_persistencia" in df_aud.columns and "mes_vida" in df_aud.columns:
            _df_fp = df_aud[df_aud["fator_persistencia"] > 0]
            if not _df_fp.empty and "produto_atuarial" in _df_fp.columns:
                _persist_meses = (
                    _df_fp.groupby(["produto_atuarial", "mes_vida"])["fator_persistencia"]
                    .mean()                       # um valor por (produto, mês)
                    .groupby(level="produto_atuarial").sum()   # ∑P(t) por produto
                    .mean()                       # média entre produtos selecionados
                )

        _kc1, _kc2, _kc3, _kc4 = st.columns(4)
        with _kc1:
            st.metric("📦 Estoque Inicial (mês 0)", f"{_qtd_ini:,.0f}")
        with _kc2:
            if _persist_meses is not None:
                st.metric("📅 Persistência Média", f"{_persist_meses:.1f} meses")
        with _kc3:
            st.metric("🏦 Prêmio Ganho (total)", f"{_pg:,.0f}")
        with _kc4:
            st.metric("⚠️ Sinistros (total)", f"{_sin:,.0f}")

        st.markdown("---")

        # ── Decaimento de Certificados por Mês de Vida ───────────
        if "mes_vida" in df_aud.columns:
            st.subheader("📉 Decaimento de Certificados")
            st.caption("Mostra como o volume de certificados decai ao longo do eixo selecionado — o efeito da curva de persistência/cancelamento.")

            _opcoes_eixo = {"Mês de Vida": "mes_vida", "Ano / Mês": "mes_projecao"}
            _opcoes_disponiveis = {k: v for k, v in _opcoes_eixo.items() if v in df_aud.columns}
            _eixo_label = st.radio(
                "Eixo X",
                options=list(_opcoes_disponiveis.keys()),
                horizontal=True,
                key="decay_eixo_x",
            )
            _eixo_col = _opcoes_disponiveis[_eixo_label]

            df_decay = decaimento_certificados(df_aud, eixo_x=_eixo_col)

            if not df_decay.empty:
                import plotly.express as px

                _color_col = "produto_atuarial" if "produto_atuarial" in df_decay.columns else None
                _fig_decay = px.line(
                    df_decay,
                    x=_eixo_col,
                    y="quantidade_certificados",
                    color=_color_col,
                    markers=True,
                    title=f"Evolução da Quantidade de Certificados por {_eixo_label}",
                    labels={
                        _eixo_col: _eixo_label,
                        "quantidade_certificados": "Qtd. Certificados",
                        "produto_atuarial": "Produto",
                    },
                )
                st.plotly_chart(_fig_decay, width="stretch")

                with st.expander("Ver tabela de decaimento"):
                    st.dataframe(df_decay, width="stretch")

            st.markdown("---")

        # ── Posição por Mês de Projeção ──────────────────────────
        st.subheader("📅 Posição por Mês de Projeção")
        st.caption("Valores financeiros agrupados por mês e produto ao longo do horizonte de projeção.")
        df_pos = posicao_por_mes(df_aud)
        if not df_pos.empty:
            st.dataframe(df_pos, width="stretch", height=400)

        st.markdown("---")

        # ── Etapas Financeiras ───────────────────────────────────
        st.subheader("📑 Etapas Financeiras (Acumulado Total)")
        st.caption("Sumário de cada etapa do cálculo — do prêmio emitido até o NPBT, antes da consolidação final.")
        df_etapas = etapas_financeiras(df_aud)
        if not df_etapas.empty:
            def _fmt_etapas(val):
                if isinstance(val, (int, float)) and not pd.isna(val):
                    return f"{val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return val if val is not None else ""

            df_etapas_fmt = df_etapas.copy()
            df_etapas_fmt["Total (acumulado)"] = df_etapas_fmt["Total (acumulado)"].apply(_fmt_etapas)
            st.dataframe(df_etapas_fmt, width="stretch", hide_index=True)

        st.markdown("---")

        st.subheader("📋 Dados Brutos de Auditoria")
        st.dataframe(df_aud, width="stretch", height=400)


# ═══════════════════════════════════════════════════════
# TAB 6 — GUIDELINE
# ═══════════════════════════════════════════════════════
with tab6:
    st.header("📖 Guideline — Metodologia de Cálculo")
    st.caption("Documentação completa das fórmulas, hipóteses e fluxo de cálculo do Budget Engine.")

    with st.expander("📐 Visão Geral do Fluxo", expanded=True):
        st.markdown("""
**Pipeline de cálculo (ordem de execução):**

```
Stock + New Business
        ↓
  Expansão mês a mês (stock_processor / nb_processor)
        ↓
  Persistência / Cancelamento (persistencia.py)
        ↓
  Prêmio Ganho + PPNG
        ↓
  Sinistros (por hipótese)
        ↓
  Comissão + Gastos + Other NBI
        ↓
  Variáveis Custom (opcional)
        ↓
  NPBT Local  ──→  (se IFRS17) CSM + RA + LRC/LIC → NPBT IFRS17
```
""")

    with st.expander("🏦 Prêmio Ganho e PPNG"):
        st.markdown("""
### Prêmio Mensal (PM)
- **Prêmio Ganho** = Prêmio Emitido por mês (já é mensal por natureza)
- **PPNG** = 0 (PM não gera reserva de PPNG)

### Prêmio Único (PU)
- **Prêmio Ganho no mês** = `valor_ppng × (dias_decorridos_no_mês / dias_total_vigência)`
- **PPNG** = Parcela ainda não reconhecida como receita
  - `PPNG_mês = PPNG_mês_anterior − prêmio_ganho_mês`

**Exemplo PU:**
- Apólice emitida em 01/01/2026, vigência 12 meses, prêmio = R$ 1.200
- Prêmio ganho em janeiro = `1.200 × (31/365) = R$ 101,92`
- PPNG no fim de janeiro = `1.200 − 101,92 = R$ 1.098,08`
""")

    with st.expander("⚠️ Sinistros"):
        st.markdown("""
### Tipos de Hipótese

| tipo_hipotese | Fórmula |
|---|---|
| `percentual_premio_ganho` | `sinistro = prêmio_ganho × valor` |
| `valor_fixo` | `sinistro = valor × quantidade_certificados` |
| `frequencia_severidade` | `sinistro = frequencia × severidade_media × quantidade_certificados` |

**Exemplo percentual:**
- Hipótese: 35% do prêmio ganho
- Prêmio ganho = R$ 100.000
- Sinistro calculado = `100.000 × 0,35 = R$ 35.000`

**Exemplo frequência × severidade:**
- Frequência = 2% (2 sinistros a cada 100 certificados)
- Severidade média = R$ 5.000
- Quantidade = 1.000 certificados
- Sinistro = `0,02 × 5.000 × 1.000 = R$ 100.000`
""")

    with st.expander("💳 Comissão"):
        st.markdown("""
### Tipos de Regra

| tipo_regra | Fórmula |
|---|---|
| `percentual_premio_emitido` | `comissão = prêmio_emitido × valor` |
| `percentual_premio_ganho` | `comissão = prêmio_ganho × valor` |
| `valor_fixo` | `comissão = valor × quantidade_certificados` |

**Exemplo:**
- Regra: 10% do prêmio emitido
- Prêmio emitido = R$ 200.000
- Comissão = `200.000 × 0,10 = R$ 20.000`
""")

    with st.expander("🏢 Gastos e Other NBI"):
        st.markdown("""
### Campos de gastos.csv

| Campo | Descrição |
|---|---|
| `tipo_gasto` | `gastos` ou `other_nbi` (ou custom_*) |
| `tipo_regra` | mesmas opções da comissão |
| `valor` | percentual ou valor fixo |

- **Gastos**: despesas operacionais alocadas ao produto
- **Other NBI**: outros itens que impactam NBI mas não são sinistro/comissão/gasto

**Exemplo Other NBI fixo:**
- tipo_regra = `valor_fixo`, valor = 500
- Quantidade = 200 certificados
- Other NBI = `500 × 200 = R$ 100.000`
""")

    with st.expander("🔄 Persistência e Cancelamento"):
        st.markdown("""
### Curva de Persistência
Define o % de certificados que permanecem ativos em cada mês de vida da apólice.

```
mes_vida | persistencia
0        | 1,00   (100% na emissão)
1        | 0,97   (97% no 1º mês após emissão)
2        | 0,95
...
12       | 0,80
24       | 0,00   (todos cancelados no mês 24)
```

### Fator mensal
`fator = persistencia[mes_vida + 1] / persistencia[mes_vida]`

### Aplicação por tipo de prêmio

**PM (Prêmio Mensal):**
- Prêmio emitido, ganho, sinistros, comissão, gastos: todos × fator acumulado
- PPNG = 0

**PU (Prêmio Único):**
- Certificados que cancelam liberam a PPNG restante (meses futuros)
- Prêmio ganho dos cancelados = proporcional aos dias decorridos até o cancelamento
  - `ganho_cancelados = ticket_médio × qtd × fator_cancelamento × (dias_decorridos / dias_no_mês)`

**Exemplo:**
- 1.000 certificados, persistência: mês 0 = 1,0 / mês 1 = 0,95
- Fator de cancelamento no mês 1 = `1,0 − 0,95 = 0,05` (50 certificados cancelam)
- Prêmio ganho dos 50 cancelados no meio do mês (15/30 dias) = `ticket × 50 × 0,5`
""")

    with st.expander("📊 NPBT Local"):
        st.markdown("""
### Fórmula

```
NPBT Local = Prêmio Ganho
           − Sinistros
           − Comissão
           − Gastos
           − Other NBI
```

**Exemplo:**
| Linha | Valor |
|---|---|
| Prêmio Ganho | R$ 1.000.000 |
| (-) Sinistros | R$ 350.000 |
| (-) Comissão | R$ 100.000 |
| (-) Gastos | R$ 80.000 |
| (-) Other NBI | R$ 20.000 |
| **= NPBT Local** | **R$ 450.000** |
""")

    with st.expander("📋 IFRS17 — CSM, RA, LRC, LIC"):
        st.markdown("""
### PAA — Premium Allocation Approach
Simplificação permitida para contratos de cobertura ≤ 12 meses.

- **LRC** (Liability for Remaining Coverage) = PPNG + RA
- **LIC** (Liability for Incurred Claims) = Sinistros ocorridos
- **Receita IFRS17** = Prêmio Ganho (igual ao local no PAA)

### CSM — Contractual Service Margin
Margem de serviço contratual: lucro não ganho reconhecido ao longo da cobertura.

```
CSM bruto = Prêmio Ganho − Sinistros − Comissão − Gastos − Other NBI
CSM amortizado no mês = CSM bruto × (dias_no_mês / duração_restante)
```

### RA — Risk Adjustment
Compensação pela incerteza dos fluxos não-financeiros.

```
RA = percentual_ra × Prêmio Ganho
```
(percentual configurável — padrão: 5%)

### NPBT IFRS17

```
NPBT IFRS17 = Receita IFRS17
            − Sinistros
            − Comissão
            − Gastos
            − Other NBI
            + CSM Amortizado
            − Risk Adjustment
```

**Exemplo com IFRS17:**
| Linha | Local | IFRS17 |
|---|---|---|
| Prêmio Ganho / Receita | R$ 1.000.000 | R$ 1.000.000 |
| (-) Sinistros | R$ 350.000 | R$ 350.000 |
| (-) Comissão | R$ 100.000 | R$ 100.000 |
| (-) Gastos | R$ 80.000 | R$ 80.000 |
| (-) Other NBI | R$ 20.000 | R$ 20.000 |
| (+) CSM Amortizado | — | R$ 38.000 |
| (-) Risk Adjustment | — | R$ 50.000 |
| **= NPBT** | **R$ 450.000** | **R$ 438.000** |
""")

    with st.expander("🔧 Variáveis Custom"):
        st.markdown("""
### Node Builder
Monte graficamente o fluxo:
`Entrada (coluna)` → `Operação (×, +, %, etc.)` → `Saída (nova variável)`

### Fórmula Livre
Escreva expressões Python usando as colunas do DataFrame:

```python
# Exemplo: Sinistralidade
df["sinistralidade"] = df["sinistros_calculado"] / df["premio_ganho_calculado"]

# Exemplo: Combined ratio
df["combined_ratio"] = (
    df["sinistros_calculado"] + df["comissao_calculada"] + df["gastos_calculado"]
) / df["premio_ganho_calculado"]
```

As variáveis criadas aparecem no output final e no P&L se adicionadas ao demonstrativo.
""")

    with st.expander("📁 Estrutura dos Arquivos de Input"):
        st.markdown("""
### Padrão CSV
- Separador: `;`
- Decimal: `,`
- Encoding: UTF-8

### stock.csv / new_business.csv
| Coluna | Tipo | Obrigatório |
|---|---|---|
| fonte | STRING | ✅ |
| safra | STRING (AAAA/MM) | ✅ |
| data_fim_mes | DATE (DD/MM/AAAA) | ✅ |
| data_ini_mes | DATE (DD/MM/AAAA) | ✅ |
| produto_atuarial | INT | ✅ |
| businessline | STRING | ✅ |
| safra_venda | STRING (AAAA/MM) | ✅ |
| tipo_premio | STRING (PM ou PU) | ✅ |
| valor_premio_emitido | FLOAT | ✅ |
| valor_comissao | FLOAT | ✅ |
| data_inicio_vigencia | DATE (DD/MM/AAAA) | ✅ |
| data_fim_vigencia | DATE (DD/MM/AAAA) | ✅ |
| quantidade_certificados | INT | ✅ |

### sinistros.csv
`produto_atuarial;businessline;tipo_hipotese;valor;frequencia;severidade_media`

**tipo_hipotese válidos:** `percentual_premio_ganho` | `valor_fixo` | `frequencia_severidade`

### comissao.csv
`produto_atuarial;businessline;tipo_regra;valor`

**tipo_regra válidos:** `percentual_premio_emitido` | `percentual_premio_ganho` | `valor_fixo`

### gastos.csv
`produto_atuarial;businessline;tipo_gasto;tipo_regra;valor`

**tipo_gasto válidos:** `gastos` | `other_nbi` | `custom_*`
""")

# ═══════════════════════════════════════════════════════
# AUTO-SAVE — persiste params+fallbacks a cada mudança
# Usa arquivo auxiliar .params.json (operação rápida, não reescreve o zip)
# ═══════════════════════════════════════════════════════
_vid_as = (st.session_state.get("sessao_carregada") or {}).get("id")
if _vid_as:
    import json as _json_as
    _params_as = {
        "mes_base":             st.session_state.get("mes_base_config", ""),
        "visao":                st.session_state.get("_sp_visao", "LOCAL"),
        "usar_paa":             st.session_state.get("_sp_usar_paa", True),
        "taxa_desconto":        float(st.session_state.get("_sp_taxa", 0.0)),
        "percentual_ra":        float(st.session_state.get("_sp_pra", 0.05)),
        "horizonte_por_produto": st.session_state.get("horizonte_por_produto", {"default": 12}),
        "max_meses_total":      int(st.session_state.get("max_meses_total", 120)),
        "pasta_fonte":          st.session_state.get("pasta_fonte", ""),
        "fallbacks":            _coletar_fallbacks_estado(),
    }
    try:
        _hash_as = hash(_json_as.dumps(_params_as, sort_keys=True, default=str))
    except Exception:
        _hash_as = None
    if _hash_as is not None and _hash_as != st.session_state.get("_auto_save_hash"):
        try:
            salvar_params_na_versao(_vid_as, _params_as)
            st.session_state["_auto_save_hash"] = _hash_as
        except Exception:
            pass
