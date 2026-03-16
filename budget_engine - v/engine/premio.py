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
    """Aplica cálculo de prêmio ganho e PPNG no DataFrame."""
    df = df.copy()
    df["premio_ganho_calculado"] = df.apply(calcular_premio_ganho, axis=1)
    df["ppng_calculado"] = df.apply(calcular_ppng, axis=1)
    return df
