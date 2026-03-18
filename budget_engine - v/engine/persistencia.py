"""
Engine de Persistência — Curvas de Cancelamento por Produto
Aplica curvas de sobrevivência mês a mês sobre Stock e New Business.

Lógica geral:
  - Curva: {produto: {mes_vida: pct}} ex: {0: 1.0, 1: 0.97, ..., 16: 0.0}
  - Mês de vida = datediff(data_inicio_vigencia, data_fim_mes_projetado) em meses completos
  - NB    : fator_abs = P(mes_vida) / P(0)           — começa de 100%, decai
  - Stock : fator_abs = P(mes_vida) / P(mes_vida_base) — posição já é "net", aplica só o delta
  - mes_vida_base para Stock é armazenado como coluna pelo stock_processor durante a expansão
"""
import pandas as pd
import numpy as np
from pathlib import Path


# ─────────────────────────────────────────────────────
# Carregar curvas de persistência do Excel
# ─────────────────────────────────────────────────────

def carregar_persistencia_excel(filepath: str) -> dict:
    """
    Lê o Excel de persistência.
    Estrutura esperada: uma aba por produto OU colunas:
        produto_atuarial | mes_vida | persistencia

    Retorna dict: {produto_atuarial: {mes_vida: pct_persistencia}}
    Exemplo: {1001: {0: 1.0, 1: 0.97, 2: 0.95, ..., 24: 0.0}}
    """
    try:
        df = pd.read_excel(filepath, sheet_name=0)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        if "produto_atuarial" in df.columns and "mes_vida" in df.columns and "persistencia" in df.columns:
            return _df_para_dict(df)

        elif "produto_atuarial" in df.columns:
            return _df_wide_para_dict(df)

        else:
            xls = pd.ExcelFile(filepath)
            resultado = {}
            for sheet in xls.sheet_names:
                try:
                    produto_id = int(sheet)
                    df_aba = pd.read_excel(filepath, sheet_name=sheet)
                    df_aba.columns = [c.strip().lower().replace(" ", "_") for c in df_aba.columns]
                    if "mes_vida" in df_aba.columns and "persistencia" in df_aba.columns:
                        resultado[produto_id] = dict(zip(
                            df_aba["mes_vida"].astype(int),
                            df_aba["persistencia"].astype(float)
                        ))
                except (ValueError, KeyError):
                    continue
            return resultado

    except Exception as e:
        raise ValueError(f"Erro ao carregar persistência: {e}")


def _df_para_dict(df: pd.DataFrame) -> dict:
    resultado = {}
    for prod, grupo in df.groupby("produto_atuarial"):
        resultado[int(prod)] = dict(zip(
            grupo["mes_vida"].astype(int),
            grupo["persistencia"].astype(float)
        ))
    return resultado


def _df_wide_para_dict(df: pd.DataFrame) -> dict:
    resultado = {}
    for _, row in df.iterrows():
        produto = int(row["produto_atuarial"])
        curva = {}
        for col in df.columns:
            if col == "produto_atuarial":
                continue
            try:
                mes = int(col)
                curva[mes] = float(row[col])
            except (ValueError, TypeError):
                continue
        resultado[produto] = curva
    return resultado


def persistencia_padrao(n_meses: int = 24, pct_inicial: float = 1.0,
                         decaimento_mensal: float = 0.02) -> dict:
    curva = {}
    for m in range(n_meses + 1):
        val = max(0.0, pct_inicial - m * decaimento_mensal)
        curva[m] = round(val, 6)
        if val <= 0:
            break
    return curva


# ─────────────────────────────────────────────────────
# Calcular mês de vida
# ─────────────────────────────────────────────────────

def calcular_mes_vida(data_inicio_vigencia, data_fim_mes_projetado) -> int:
    if pd.isnull(data_inicio_vigencia) or pd.isnull(data_fim_mes_projetado):
        return 0
    d_ini = pd.Timestamp(data_inicio_vigencia)
    d_fim = pd.Timestamp(data_fim_mes_projetado)
    meses = (d_fim.year - d_ini.year) * 12 + (d_fim.month - d_ini.month)
    return max(0, meses)


def fator_persistencia(curva: dict, mes_vida_atual: int) -> float:
    p_atual = curva.get(mes_vida_atual, None)
    p_prox  = curva.get(mes_vida_atual + 1, None)
    if p_atual is None or p_atual <= 0:
        return 0.0
    if p_prox is None:
        return 0.0
    return p_prox / p_atual


def persistencia_absoluta(curva: dict, mes_vida: int) -> float:
    return curva.get(mes_vida, 0.0)


# ─────────────────────────────────────────────────────
# Colunas
# ─────────────────────────────────────────────────────

COLUNAS_MONETARIAS = [
    "valor_premio_emitido",
    "valor_comissao",
    "comissao_calculada",
    "sinistros_calculado",
    "gastos_calculado",
    "other_nbi_calculado",
    "montante_capital",
]

COLUNAS_PPNG = ["ppng_calculado", "valor_ppng"]

COLUNAS_PREMIO_GANHO = ["premio_ganho_calculado", "valor_premio_ganho_mes"]


# ─────────────────────────────────────────────────────
# Aplicar persistência — versão vetorizada
# ─────────────────────────────────────────────────────

def aplicar_persistencia_acumulada(
    df_base: pd.DataFrame,
    curvas: dict,
    produto_col: str = "produto_atuarial",
    fallback_curva: dict = None,
) -> pd.DataFrame:
    """
    Aplica persistência de forma vetorizada (muito mais rápida que apply row-by-row).

    Lógica de âncora:
      - NB    (sem 'mes_vida_stock_base'): fator = P(mes_vida) / P(0)
      - Stock (com 'mes_vida_stock_base'): fator = P(mes_vida) / P(mes_vida_base)
        → Porque o Stock já vem com posição "net" (68% = já cancelou 32%).
          A projeção deve apenas aplicar o DELTA adicional de cancelamento.

    Exemplo Stock:
      mes_base m=18 com P(18)=68%, m=19 P(19)=66%
      fator_abs m=18 = 68%/68% = 1.0  (mantém o valor atual)
      fator_abs m=19 = 66%/68% = 0.97 (perde 2% deste mês em diante)
    """
    df = df_base.copy()

    if df.empty:
        return df

    # Normaliza datas
    for col in ["data_inicio_vigencia", "data_ini_primeira_vigencia", "data_ini_mes", "data_fim_mes"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    qtd_col = "quantidade_certificados"

    # ── Monta curvas efetivas por produto (com fallback) ──
    all_prods = df[produto_col].dropna().unique()
    curvas_efetivas = {}
    for p in all_prods:
        try:
            pk = int(float(p))
        except (ValueError, TypeError):
            pk = p
        c = curvas.get(pk, curvas.get(str(pk), None))
        if c is None and fallback_curva:
            c = fallback_curva
        if c:
            curvas_efetivas[pk] = c

    if not curvas_efetivas:
        return df  # Nenhuma curva → sem cancelamento

    # ── Tabela de lookup: (produto_int, mes_vida) → (p_m, p_m1) ──
    lookup_rows = []
    for pk, curva in curvas_efetivas.items():
        for mv, pm in curva.items():
            lookup_rows.append({
                "_pk":     int(pk),
                "mes_vida": int(mv),
                "_p_m":    float(pm),
                "_p_m1":   float(curva.get(mv + 1, 0.0)),
            })
    if not lookup_rows:
        return df
    df_lookup = pd.DataFrame(lookup_rows)

    # ── Tabela de p_base: (produto_int, mes_vida_base) → p_base ──
    df_lookup_base = df_lookup[["_pk", "mes_vida", "_p_m"]].rename(
        columns={"mes_vida": "_mvb", "_p_m": "_p_base"}
    )

    # ── Calcula mes_vida para cada linha ──
    if "data_ini_primeira_vigencia" in df.columns:
        d_ini = df["data_ini_primeira_vigencia"].fillna(
            df["data_inicio_vigencia"] if "data_inicio_vigencia" in df.columns else pd.NaT
        )
    elif "data_inicio_vigencia" in df.columns:
        d_ini = df["data_inicio_vigencia"]
    else:
        d_ini = pd.Series(pd.NaT, index=df.index)

    d_fim = df["data_fim_mes"] if "data_fim_mes" in df.columns else pd.Series(pd.NaT, index=df.index)

    mv_series = (
        (d_fim.dt.year  - d_ini.dt.year)  * 12 +
        (d_fim.dt.month - d_ini.dt.month)
    ).clip(lower=0).fillna(0).astype(int)
    df["mes_vida"] = mv_series

    # ── Chave inteira do produto ──
    df["_pk"] = pd.to_numeric(df[produto_col], errors="coerce").fillna(0).astype(int)

    # ── Merge p_m e p_m1 ──
    df = df.merge(
        df_lookup[["_pk", "mes_vida", "_p_m", "_p_m1"]],
        on=["_pk", "mes_vida"], how="left"
    )

    # ── p0 por produto (âncora NB = P(0)) ──
    p0_map = {int(pk): float(c.get(0, 1.0)) for pk, c in curvas_efetivas.items()}
    df["_p0"] = df["_pk"].map(p0_map)

    # ── p_anchor: Stock usa P(mes_vida_base), NB usa P(0) ──
    has_stock_col = ("mes_vida_stock_base" in df.columns and
                     df["mes_vida_stock_base"].notna().any())
    if has_stock_col:
        df["_mvb"] = df["mes_vida_stock_base"].fillna(-1).astype(int)
        df = df.merge(
            df_lookup_base[["_pk", "_mvb", "_p_base"]],
            on=["_pk", "_mvb"], how="left"
        )
        is_stock = df["mes_vida_stock_base"].notna()
        df["_p_anchor"] = np.where(
            is_stock,
            df["_p_base"].fillna(1.0),
            df["_p0"].fillna(1.0)
        )
    else:
        df["_p_anchor"] = df["_p0"].fillna(1.0)

    # ── Fatores ──
    # tem_curva_produto: o produto tem uma curva configurada (pode não ter entrada para este mes_vida)
    # has_curva_entry: a entrada (produto, mes_vida) existe no lookup
    # Distinção importante:
    #   - produto SEM curva → sem cancelamento (fator = 1.0)
    #   - produto COM curva mas mes_vida além da curva → cancelado (fator = 0.0)
    #   - produto COM curva e mes_vida na curva → usa p_m / p_anchor
    produtos_com_curva = set(curvas_efetivas.keys())
    tem_curva_produto = df["_pk"].isin(produtos_com_curva).values
    has_curva_entry   = df["_p_m"].notna().values

    p_m      = df["_p_m"].fillna(0.0).values
    p_m1     = df["_p_m1"].fillna(0.0).values
    p_anchor = df["_p_anchor"].clip(lower=1e-10).values

    # fator_abs:
    #   produto sem curva       → 1.0
    #   produto com curva, sem entrada no mes_vida → 0.0 (além da curva = cancelado)
    #   produto com curva, com entrada → p_m / p_anchor
    fator_abs = np.where(
        ~tem_curva_produto,
        1.0,
        np.where(
            has_curva_entry,
            np.where(p_anchor > 0, p_m / p_anchor, 0.0),
            0.0
        )
    )
    fator_prox = np.where(
        ~tem_curva_produto,
        1.0,
        np.where(
            has_curva_entry,
            np.where(p_anchor > 0, p_m1 / p_anchor, 0.0),
            0.0
        )
    )
    fator_cancel = np.maximum(fator_abs - fator_prox, 0.0)
    cancelled    = tem_curva_produto & (fator_abs <= 0)

    df["fator_persistencia"] = fator_abs

    # ── tipo_premio ──
    if "tipo_premio" in df.columns:
        tipo_prem = df["tipo_premio"].fillna("PM").astype(str).str.upper().str.strip()
    else:
        tipo_prem = pd.Series("PM", index=df.index)
    is_pm = (tipo_prem == "PM").values
    is_pu = (tipo_prem == "PU").values

    # ── Quantidade original ──
    if qtd_col in df.columns:
        qtd_orig = df[qtd_col].copy()
        qtd_orig = qtd_orig.where(qtd_orig > 0, 1.0)
    else:
        qtd_orig = pd.Series(1.0, index=df.index)

    # ── Dias proporcional (para prêmio ganho no mês de cancelamento) ──
    if "data_ini_mes" in df.columns and "data_fim_mes" in df.columns:
        dias_no_mes = ((df["data_fim_mes"] - df["data_ini_mes"]).dt.days + 1).clip(lower=1)
    else:
        dias_no_mes = pd.Series(30, index=df.index)

    if "duration_decorrido_mes" in df.columns:
        dias_decorr = pd.to_numeric(df["duration_decorrido_mes"], errors="coerce").fillna(dias_no_mes)
    else:
        dias_decorr = dias_no_mes

    fator_dias = (dias_decorr / dias_no_mes).clip(upper=1.0).values

    fa  = np.array(fator_abs)
    fp  = np.array(fator_prox)
    fc  = np.array(fator_cancel)
    qo  = qtd_orig.values

    # ── Colunas monetárias ──
    for c in COLUNAS_MONETARIAS:
        if c in df.columns:
            ticket = df[c].values / qo
            df[c] = np.where(cancelled, 0.0, ticket * qo * fa)

    # ── PPNG (só PU) ──
    for c in COLUNAS_PPNG:
        if c in df.columns:
            ticket = df[c].values / qo
            df[c] = np.where(cancelled, 0.0,
                     np.where(is_pu, ticket * qo * fa, 0.0))

    # ── Prêmio ganho ──
    for c in COLUNAS_PREMIO_GANHO:
        if c in df.columns:
            ticket = df[c].values / qo
            ganho_pm = ticket * qo * fa
            ganho_pu = ticket * qo * fp + ticket * qo * fc * fator_dias
            df[c] = np.where(cancelled, 0.0,
                     np.where(is_pm, ganho_pm, ganho_pu))

    # ── Quantidade final ──
    if qtd_col in df.columns:
        df[qtd_col] = np.where(cancelled, 0.0, qo * fa)

    # ── Remove linhas canceladas ──
    df = df[df["fator_persistencia"] > 0].copy()

    # ── Limpa colunas temporárias ──
    tmp = ["_pk", "_p_m", "_p_m1", "_p0", "_p_anchor", "_p_base", "_mvb"]
    df = df.drop(columns=[c for c in tmp if c in df.columns], errors="ignore")

    return df


# ─────────────────────────────────────────────────────
# Gerar Excel template de persistência
# ─────────────────────────────────────────────────────

def gerar_template_persistencia(produtos: list, n_meses: int = 24,
                                  filepath: str = "persistencia_template.xlsx"):
    rows = []
    for prod in produtos:
        for m in range(n_meses + 1):
            pct = max(0.0, round(1.0 - m * (1.0 / n_meses), 4))
            rows.append({
                "produto_atuarial": prod,
                "mes_vida": m,
                "persistencia": pct
            })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Persistencia")
        pd.DataFrame({
            "Instrucoes": [
                "Preencha uma linha por produto por mês de vida (0 até o máximo desejado).",
                "mes_vida: 0 = mês de emissão, 1 = primeiro mês após emissão, etc.",
                "persistencia: valor entre 0 e 1 (ex: 0.97 = 97% ainda ativos).",
                "Quando persistencia = 0, o certificado é cancelado e não projetado mais.",
                "A curva pode ir até 120 meses.",
                "Produtos sem curva definida usarão o fallback padrão configurado no painel.",
            ]
        }).to_excel(writer, index=False, sheet_name="Instrucoes")

    print(f"Template gerado: {filepath}")
    return filepath
