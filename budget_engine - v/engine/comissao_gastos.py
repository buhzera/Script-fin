"""
Engine de Comissão e Gastos
Suporta regras variáveis por produto, businessline e intervalo de meses

Suporte a hipóteses por período:
  - Linhas sem periodo_inicio = regra global (todos os períodos)
  - Linhas com periodo_inicio/periodo_fim = sobrescreve a regra global para aquele intervalo
    Ex: periodo_inicio=2026/01, periodo_fim=2026/12 cobre todos os meses de 2026
        periodo_inicio=2028/01, periodo_fim vazio = apenas janeiro/2028
"""
import pandas as pd
import numpy as np


# ─────────────────────────────────────────
# helpers compartilhados
# ─────────────────────────────────────────

def _expandir_periodos(hipoteses: pd.DataFrame) -> pd.DataFrame:
    """
    Converte linhas com periodo_inicio/periodo_fim em linhas individuais por mes_projecao.
    Linhas sem periodo_inicio = regra global (mes_projecao vazio).
    """
    if "periodo_inicio" not in hipoteses.columns:
        return hipoteses.copy()

    mask_global = (
        hipoteses["periodo_inicio"].isna()
        | (hipoteses["periodo_inicio"].astype(str).str.strip() == "")
    )
    hip_global = hipoteses[mask_global].copy()
    hip_period = hipoteses[~mask_global].copy()

    expanded = []
    for _, row in hip_period.iterrows():
        ini_str = str(row["periodo_inicio"]).strip()
        fim_str = str(row.get("periodo_fim", "")).strip()
        if not fim_str or fim_str.lower() == "nan":
            fim_str = ini_str
        try:
            ini = pd.Period(ini_str, freq="M")
            fim = pd.Period(fim_str, freq="M")
            for p in pd.period_range(ini, fim, freq="M"):
                new_row = row.copy()
                new_row["mes_projecao"] = p.strftime("%Y/%m")
                expanded.append(new_row)
        except Exception:
            pass

    cols_drop = ["periodo_inicio", "periodo_fim"]
    hip_global = hip_global.drop(columns=cols_drop, errors="ignore")
    if "mes_projecao" not in hip_global.columns:
        hip_global["mes_projecao"] = ""

    if expanded:
        exp_df = pd.DataFrame(expanded).drop(columns=cols_drop, errors="ignore")
        return pd.concat([hip_global, exp_df], ignore_index=True)
    return hip_global


def _split_periodo(hipoteses: pd.DataFrame):
    """Divide em regras por período específico e regras globais."""
    has_periodo = (
        "mes_projecao" in hipoteses.columns
        and hipoteses["mes_projecao"].notna().any()
        and (hipoteses["mes_projecao"].astype(str).str.strip() != "").any()
    )
    if not has_periodo:
        return pd.DataFrame(), hipoteses.copy()
    mask_p = hipoteses["mes_projecao"].notna() & (hipoteses["mes_projecao"].astype(str).str.strip() != "")
    return hipoteses[mask_p].copy(), hipoteses[~mask_p].copy()


# ─────────────────────────────────────────
# COMISSÃO
# ─────────────────────────────────────────

def carregar_hipoteses_comissao(filepath: str) -> pd.DataFrame:
    """
    Estrutura esperada:
    produto_atuarial | businessline | tipo_regra | valor | periodo_inicio (opcional) | periodo_fim (opcional)
    tipo_regra: percentual_premio_emitido | percentual_premio_ganho | valor_fixo
    """
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def aplicar_comissao(df: pd.DataFrame, hipoteses: pd.DataFrame, fallback: dict = None) -> pd.DataFrame:
    df = df.copy()
    hipoteses = _expandir_periodos(hipoteses)
    hip_periodo, hip_global = _split_periodo(hipoteses)

    # Merge global
    df = df.merge(
        hip_global[["produto_atuarial", "businessline", "tipo_regra", "valor"]].rename(
            columns={"tipo_regra": "_tr_g", "valor": "_val_g"}
        ),
        on=["produto_atuarial", "businessline"],
        how="left",
    )

    # Merge por período
    if not hip_periodo.empty and "mes_projecao" in df.columns:
        df = df.merge(
            hip_periodo[["produto_atuarial", "businessline", "mes_projecao", "tipo_regra", "valor"]].rename(
                columns={"tipo_regra": "_tr_p", "valor": "_val_p"}
            ),
            on=["produto_atuarial", "businessline", "mes_projecao"],
            how="left",
        )
        has_p = df["_tr_p"].notna()
        df["_tr"]  = np.where(has_p, df["_tr_p"],  df["_tr_g"])
        df["_val"] = np.where(has_p, df["_val_p"], df["_val_g"])
        df.drop(columns=["_tr_p", "_val_p", "_tr_g", "_val_g"], errors="ignore", inplace=True)
    else:
        df.rename(columns={"_tr_g": "_tr", "_val_g": "_val"}, inplace=True)

    def calcular_comissao(row):
        tipo        = row.get("_tr", "")
        val         = row.get("_val", 0) or 0
        tipo_premio = row.get("tipo_premio", "PM")
        dur         = row.get("duration", 1) or 1
        dur_mes     = row.get("duration_decorrido_mes", 0)

        if tipo == "percentual_premio_emitido":
            comissao_emitida = row.get("valor_premio_emitido", 0) * val
            if tipo_premio == "PU":
                return (dur_mes / dur) * comissao_emitida
            return comissao_emitida
        elif tipo == "percentual_premio_ganho":
            return row.get("premio_ganho_calculado", 0) * val
        elif tipo == "valor_fixo":
            return val * row.get("quantidade_certificados", 1)
        # fallback: valor_comissao do CSV — prorate para PU, direto para PM
        comissao_csv = row.get("valor_comissao", 0)
        if tipo_premio == "PU":
            return (dur_mes / dur) * comissao_csv
        return comissao_csv

    if fallback and fallback.get("ativo"):
        no_match = df["_tr"].isna() | (df["_tr"].astype(str).str.strip() == "")
        if no_match.any():
            df.loc[no_match, "_tr"]  = fallback.get("tipo", "")
            df.loc[no_match, "_val"] = fallback.get("valor", 0)

    df["comissao_calculada"] = df.apply(calcular_comissao, axis=1)
    df.drop(columns=["_tr", "_val"], errors="ignore", inplace=True)
    return df


# ─────────────────────────────────────────
# GASTOS
# ─────────────────────────────────────────

def carregar_hipoteses_gastos(filepath: str) -> pd.DataFrame:
    """
    Estrutura esperada:
    produto_atuarial | businessline | tipo_gasto | tipo_regra | valor | periodo_inicio (opcional) | periodo_fim (opcional)
    tipo_gasto: gastos | other_nbi | custom_<nome>
    tipo_regra: percentual_premio_ganho | valor_fixo | percentual_premio_emitido
    """
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def aplicar_gastos(df: pd.DataFrame, hipoteses: pd.DataFrame, tipo_gasto: str = "gastos", fallback: dict = None) -> pd.DataFrame:
    df = df.copy()
    hip_filtrado = hipoteses[hipoteses["tipo_gasto"] == tipo_gasto].copy()
    hip_filtrado = _expandir_periodos(hip_filtrado)
    hip_periodo, hip_global = _split_periodo(hip_filtrado)

    # Merge global
    df = df.merge(
        hip_global[["produto_atuarial", "businessline", "tipo_regra", "valor"]].rename(
            columns={"tipo_regra": "_tr_g", "valor": "_val_g"}
        ),
        on=["produto_atuarial", "businessline"],
        how="left",
    )

    # Merge por período
    if not hip_periodo.empty and "mes_projecao" in df.columns:
        df = df.merge(
            hip_periodo[["produto_atuarial", "businessline", "mes_projecao", "tipo_regra", "valor"]].rename(
                columns={"tipo_regra": "_tr_p", "valor": "_val_p"}
            ),
            on=["produto_atuarial", "businessline", "mes_projecao"],
            how="left",
        )
        has_p = df["_tr_p"].notna()
        df["_tr"]  = np.where(has_p, df["_tr_p"],  df["_tr_g"])
        df["_val"] = np.where(has_p, df["_val_p"], df["_val_g"])
        df.drop(columns=["_tr_p", "_val_p", "_tr_g", "_val_g"], errors="ignore", inplace=True)
    else:
        df.rename(columns={"_tr_g": "_tr", "_val_g": "_val"}, inplace=True)

    col_resultado = f"{tipo_gasto}_calculado"

    def calcular_gasto(row):
        tipo = row.get("_tr", "")
        val  = row.get("_val", 0)
        if pd.isnull(val):
            return 0.0
        if tipo == "percentual_premio_ganho":
            return row.get("premio_ganho_calculado", 0) * val
        elif tipo == "percentual_premio_emitido":
            return row.get("valor_premio_emitido", 0) * val
        elif tipo == "valor_fixo":
            return val
        return 0.0

    if fallback and fallback.get("ativo"):
        no_match = df["_tr"].isna() | (df["_tr"].astype(str).str.strip() == "")
        if no_match.any():
            df.loc[no_match, "_tr"]  = fallback.get("tipo", "")
            df.loc[no_match, "_val"] = fallback.get("valor", 0)

    df[col_resultado] = df.apply(calcular_gasto, axis=1)
    df.drop(columns=["_tr", "_val"], errors="ignore", inplace=True)
    return df
