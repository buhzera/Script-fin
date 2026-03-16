"""
Engine de Savings — Produtos de Previdência/Capitalização

Modelo financeiro mensal:
  aporte_bruto      = aporte_medio × quantidade_certificados
  carregamento      = carregamento_por_aporte × quantidade_certificados  (receita = cobre sinistros)
  net_capital_mes   = (aporte_medio - carregamento_por_aporte) × quantidade_certificados
  montante_capital evolui mensalmente no expansion loop
  taf_calculado     = (taf_anual_pct / 12) × montante_capital  (aplicado pós-persistência)

NPBT Savings = taf_calculado + carregamento_calculado - sinistros - comissao - gastos
"""
import pandas as pd
import numpy as np


def carregar_hipoteses_savings(filepath: str) -> pd.DataFrame:
    """
    Carrega savings_hipoteses.csv.
    Colunas esperadas:
      produto_atuarial | businessline | taf_anual_pct | aporte_medio | carregamento_por_aporte
    """
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in ["taf_anual_pct", "aporte_medio", "carregamento_por_aporte"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def savings_params_dict(hipoteses: pd.DataFrame) -> dict:
    """
    Converte DataFrame de hipóteses para dict de lookup usado no expansion loop.
    Retorna {str(produto_atuarial): {"aporte_medio": x, "carregamento_por_aporte": y, "taf_anual_pct": z}}
    """
    resultado = {}
    for _, row in hipoteses.iterrows():
        produto = str(row.get("produto_atuarial", "default"))
        resultado[produto] = {
            "aporte_medio": float(row.get("aporte_medio", 0)),
            "carregamento_por_aporte": float(row.get("carregamento_por_aporte", 0)),
            "taf_anual_pct": float(row.get("taf_anual_pct", 0)),
        }
    return resultado


def aplicar_savings(df: pd.DataFrame, hipoteses: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica TAF e carregamento para linhas de Savings.
    Deve ser chamado APÓS aplicar_persistencia_acumulada.

      taf_calculado        = (taf_anual_pct / 12) × montante_capital
      carregamento_calculado = carregamento_por_aporte × quantidade_certificados
    """
    df = df.copy()

    # Inicializa colunas — Protection sempre fica 0
    df["taf_calculado"] = 0.0
    df["carregamento_calculado"] = 0.0

    if hipoteses is None or hipoteses.empty:
        return df

    mask = df["categoria"] == "Savings" if "categoria" in df.columns else pd.Series(False, index=df.index)
    if not mask.any():
        return df

    df_sav = df[mask].copy()

    # Normaliza produto_atuarial para string em ambos para evitar mismatch int/str
    hip = hipoteses.copy()
    if "produto_atuarial" in df_sav.columns:
        df_sav["produto_atuarial"] = df_sav["produto_atuarial"].astype(str)
    if "produto_atuarial" in hip.columns:
        hip["produto_atuarial"] = hip["produto_atuarial"].astype(str)

    merge_on = [c for c in ["produto_atuarial", "businessline"] if c in df_sav.columns and c in hip.columns]
    cols_hip = merge_on + [c for c in ["taf_anual_pct", "aporte_medio", "carregamento_por_aporte"]
                           if c in hip.columns]
    df_sav = df_sav.merge(hip[cols_hip], on=merge_on, how="left")

    taf_pct = pd.to_numeric(df_sav.get("taf_anual_pct", 0), errors="coerce").fillna(0)
    cap     = pd.to_numeric(df_sav.get("montante_capital", 0), errors="coerce").fillna(0)
    carr    = pd.to_numeric(df_sav.get("carregamento_por_aporte", 0), errors="coerce").fillna(0)
    qtd     = pd.to_numeric(df_sav.get("quantidade_certificados", 0), errors="coerce").fillna(0)

    df_sav["taf_calculado"]         = (taf_pct / 12) * cap
    df_sav["carregamento_calculado"] = carr * qtd

    df.loc[mask, "taf_calculado"]         = df_sav["taf_calculado"].values
    df.loc[mask, "carregamento_calculado"] = df_sav["carregamento_calculado"].values

    return df
