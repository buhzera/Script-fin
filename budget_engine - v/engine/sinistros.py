"""
Engine de Sinistros - Aplica hipóteses de sinistralidade por produto
Suporta: valor fixo, % do prêmio ganho, tabela de frequência/severidade

Suporte a hipóteses por período:
  - Linhas sem periodo_inicio = regra global (todos os períodos)
  - Linhas com periodo_inicio/periodo_fim = sobrescreve a regra global para aquele intervalo
    Ex: periodo_inicio=2026/01, periodo_fim=2026/12 cobre todos os meses de 2026
        periodo_inicio=2028/01, periodo_fim vazio = apenas janeiro/2028
"""
import pandas as pd
import numpy as np


TIPOS_HIPOTESE = ["percentual_premio_ganho", "valor_fixo", "frequencia_severidade"]


def carregar_hipoteses_sinistros(filepath: str) -> pd.DataFrame:
    """
    Estrutura esperada do CSV de hipóteses:
    produto_atuarial | businessline | tipo_hipotese | valor | frequencia | severidade_media
    | periodo_inicio (opcional) | periodo_fim (opcional)
    """
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


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


def aplicar_sinistros(df: pd.DataFrame, hipoteses: pd.DataFrame, fallback: dict = None) -> pd.DataFrame:
    """
    Aplica hipóteses de sinistros ao DataFrame principal.
    Expande intervalos periodo_inicio/periodo_fim antes do merge.
    Regras por período sobrescrevem a regra global para aqueles meses.
    """
    df = df.copy()
    hipoteses = _expandir_periodos(hipoteses)

    cols_base = ["produto_atuarial", "businessline", "tipo_hipotese", "valor", "frequencia", "severidade_media"]
    hip_periodo, hip_global = _split_periodo(hipoteses)

    # Merge global
    cols_g = [c for c in cols_base if c in hip_global.columns]
    df = df.merge(
        hip_global[cols_g].rename(columns={
            "tipo_hipotese": "_tipo_g", "valor": "_val_g",
            "frequencia": "_freq_g", "severidade_media": "_sev_g",
        }),
        on=["produto_atuarial", "businessline"],
        how="left",
    )

    # Merge por período (sobrescreve global)
    if not hip_periodo.empty and "mes_projecao" in df.columns:
        cols_p = [c for c in cols_base + ["mes_projecao"] if c in hip_periodo.columns]
        df = df.merge(
            hip_periodo[cols_p].rename(columns={
                "tipo_hipotese": "_tipo_p", "valor": "_val_p",
                "frequencia": "_freq_p", "severidade_media": "_sev_p",
            }),
            on=["produto_atuarial", "businessline", "mes_projecao"],
            how="left",
        )
        has_p = df["_tipo_p"].notna()
        df["_tipo"] = np.where(has_p, df["_tipo_p"], df["_tipo_g"])
        df["_val"]  = np.where(has_p, df["_val_p"],  df["_val_g"])
        df["_freq"] = np.where(has_p, df["_freq_p"], df.get("_freq_g", 0))
        df["_sev"]  = np.where(has_p, df["_sev_p"],  df.get("_sev_g",  0))
        df.drop(columns=["_tipo_p", "_val_p", "_freq_p", "_sev_p",
                         "_tipo_g", "_val_g", "_freq_g", "_sev_g"], errors="ignore", inplace=True)
    else:
        df.rename(columns={
            "_tipo_g": "_tipo", "_val_g": "_val",
            "_freq_g": "_freq", "_sev_g": "_sev",
        }, inplace=True)

    def _calc(row):
        tipo = row.get("_tipo", "")
        val  = row.get("_val",  0) or 0
        freq = row.get("_freq", 0) or 0
        sev  = row.get("_sev",  0) or 0
        qtd  = row.get("quantidade_certificados", 1)
        pg   = row.get("premio_ganho_calculado", 0)
        if tipo == "percentual_premio_ganho":
            return pg * val
        elif tipo == "valor_fixo":
            return val * qtd
        elif tipo == "frequencia_severidade":
            return freq * sev * qtd
        return 0.0

    # Aplica fallback onde não há hipótese cadastrada
    if fallback and fallback.get("ativo"):
        no_match = df["_tipo"].isna() | (df["_tipo"].astype(str).str.strip() == "")
        if no_match.any():
            df.loc[no_match, "_tipo"] = fallback.get("tipo", "")
            df.loc[no_match, "_val"]  = fallback.get("valor", 0)
            df.loc[no_match, "_freq"] = fallback.get("frequencia", 0)
            df.loc[no_match, "_sev"]  = fallback.get("severidade_media", 0)

    df["sinistros_calculado"] = df.apply(_calc, axis=1)
    df.drop(columns=["_tipo", "_val", "_freq", "_sev"], errors="ignore", inplace=True)
    return df
