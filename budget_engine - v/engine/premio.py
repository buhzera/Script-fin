"""
Engine de Prêmio - Cálculo de Prêmio Ganho e PPNG
Suporta PM (Prêmio Mensal) e PU (Prêmio Único)
"""
import pandas as pd
import numpy as np
from datetime import date


def calcular_premio_ganho(row: pd.Series) -> float:
    """
    Savings: sempre 0 (receita via TAF e carregamento, não prêmio ganho)
    PM: todo o prêmio emitido é ganho no mesmo mês
    PU: prêmio ganho = (duration_decorrido_mes / duration) * premio_emitido
    """
    if str(row.get("categoria", "Protection")) == "Savings":
        return 0.0
    if row["tipo_premio"] == "PM":
        return row["valor_premio_emitido"]
    elif row["tipo_premio"] == "PU":
        if row["duration"] == 0:
            return 0.0
        return (row["duration_decorrido_mes"] / row["duration"]) * row["valor_premio_emitido"]
    return 0.0


def calcular_ppng(row: pd.Series) -> float:
    """
    Savings: sempre 0
    PPNG só existe para PU: ((duration - duration_decorrido) / duration) * premio_emitido
    """
    if str(row.get("categoria", "Protection")) == "Savings":
        return 0.0
    if row["tipo_premio"] == "PU":
        if row["duration"] == 0:
            return 0.0
        duration_restante = row["duration"] - row["duration_decorrido"]
        return (duration_restante / row["duration"]) * row["valor_premio_emitido"]
    return 0.0


def aplicar_premio(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica cálculo de prêmio ganho e PPNG no DataFrame (vetorizado)."""
    df = df.copy()

    cat   = df["categoria"].astype(str)   if "categoria"           in df.columns else pd.Series("Protection",      index=df.index)
    tipo  = df["tipo_premio"].astype(str) if "tipo_premio"          in df.columns else pd.Series("PM",              index=df.index)
    prem  = pd.to_numeric(df["valor_premio_emitido"],   errors="coerce").fillna(0.0) if "valor_premio_emitido"   in df.columns else pd.Series(0.0, index=df.index)
    dur   = pd.to_numeric(df["duration"],               errors="coerce").fillna(0.0) if "duration"               in df.columns else pd.Series(0.0, index=df.index)
    durm  = pd.to_numeric(df["duration_decorrido_mes"], errors="coerce").fillna(0.0) if "duration_decorrido_mes" in df.columns else pd.Series(0.0, index=df.index)
    durd  = pd.to_numeric(df["duration_decorrido"],     errors="coerce").fillna(0.0) if "duration_decorrido"     in df.columns else pd.Series(0.0, index=df.index)

    is_sav = (cat == "Savings").values
    is_pm  = (tipo == "PM").values
    is_pu  = (tipo == "PU").values
    has_d  = (dur > 0).values

    pv  = prem.values
    dv  = np.where(has_d, dur.values, 1.0)   # evita divisão por zero
    dmv = durm.values
    ddv = durd.values

    pg = np.where(is_sav, 0.0,
         np.where(is_pm,         pv,
         np.where(is_pu & has_d, (dmv / dv) * pv, 0.0)))

    dur_rest = np.where(has_d, dur.values - ddv, 0.0)
    ppng = np.where(is_sav, 0.0,
           np.where(is_pu & has_d, (dur_rest / dv) * pv, 0.0))

    df["premio_ganho_calculado"] = pg
    df["ppng_calculado"]         = ppng
    return df
