"""
Auditoria — Super-auditor dos números
Trilha completa por produto: ponto de partida → decaimento → valores em cada etapa.

Trabalha sobre o DataFrame intermediário (pós-persistência, pré-consolidação),
que já contém: fator_persistencia, mes_vida, e todos os valores calculados.
"""
import pandas as pd
import numpy as np


CHAVES_FILTRO = [
    "produto_atuarial", "fonte", "businessline",
    "safra_venda", "tipo_premio", "movimento",
]

COLUNAS_FINANCEIRAS = [
    "quantidade_certificados",
    "montante_capital",
    "valor_premio_emitido",
    "premio_ganho_calculado",
    "taf_calculado",
    "carregamento_calculado",
    "ppng_calculado",
    "sinistros_calculado",
    "comissao_calculada",
    "gastos_calculado",
    "other_nbi_calculado",
]


def filtrar(df: pd.DataFrame, filtros: dict) -> pd.DataFrame:
    """Aplica filtros {coluna: lista_de_valores} ao DataFrame."""
    for col, valores in filtros.items():
        if col in df.columns and valores:
            df = df[df[col].isin(valores)]
    return df


def decaimento_certificados(df: pd.DataFrame, eixo_x: str = "mes_vida") -> pd.DataFrame:
    """
    Curva de decaimento de certificados por eixo_x.

    Para cada produto, mostra como o volume de certificados evolui ao longo
    do eixo escolhido:
      - "mes_vida"    : meses de vida desde o início da vigência
      - "mes_projecao": ano/mês calendário (formato AAAA/MM)

    Retorna: {eixo_x} | produto_atuarial | quantidade_certificados | fator_persistencia
    """
    if eixo_x not in df.columns:
        return pd.DataFrame()

    chaves = [c for c in [eixo_x, "produto_atuarial"] if c in df.columns]

    agg = {}
    if "quantidade_certificados" in df.columns:
        agg["quantidade_certificados"] = ("quantidade_certificados", "sum")
    if "fator_persistencia" in df.columns:
        agg["fator_persistencia"] = ("fator_persistencia", "mean")

    if not agg:
        return pd.DataFrame()

    return (
        df.groupby(chaves, dropna=False)
        .agg(**agg)
        .reset_index()
        .sort_values(eixo_x)
    )


def posicao_por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evolução temporal: agrupa por mes_projecao e produto com todos os valores
    financeiros. Mostra a fotografia de cada mês ao longo do horizonte.
    """
    chaves = [c for c in ["categoria", "mes_projecao", "produto_atuarial"] if c in df.columns]
    cols_num = [c for c in COLUNAS_FINANCEIRAS if c in df.columns]

    if not chaves or not cols_num:
        return pd.DataFrame()

    return df.groupby(chaves, dropna=False)[cols_num].sum().reset_index()


def etapas_financeiras(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sumário das etapas financeiras — linha por linha do P&L com total acumulado.
    Mostra o fluxo: Prêmio → Sinistros → Comissão → Gastos.
    """
    etapas = [
        ("Certificados (Qtd)",  "quantidade_certificados"),
        ("Montante Capital",    "montante_capital"),
        ("Prêmio Emitido",      "valor_premio_emitido"),
        ("Prêmio Ganho",        "premio_ganho_calculado"),
        ("TAF (Savings)",       "taf_calculado"),
        ("Carregamento (Sav.)", "carregamento_calculado"),
        ("PPNG",                "ppng_calculado"),
        ("(-) Sinistros",       "sinistros_calculado"),
        ("(-) Comissão",        "comissao_calculada"),
        ("(-) Gastos",          "gastos_calculado"),
        ("(-) Other NBI",       "other_nbi_calculado"),
    ]
    rows = []
    for label, col in etapas:
        if col in df.columns:
            rows.append({"Etapa": label, "Total (acumulado)": df[col].sum()})
    return pd.DataFrame(rows)
