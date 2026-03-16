"""
Resultado Final - Consolida todas as linhas até NPBT
Gera output CSV com visão LOCAL e/ou IFRS17
"""
import pandas as pd
import numpy as np
from engine.ifrs17 import aplicar_ifrs17


COLUNAS_CHAVE = [
    "mes_projecao", "fonte", "produto_atuarial",
    "businessline", "safra_venda", "tipo_premio"
]

COLUNAS_RESULTADO = [
    "valor_premio_emitido",
    "premio_ganho_calculado",
    "ppng_calculado",
    "sinistros_calculado",
    "comissao_calculada",
    "gastos_calculado",
    "other_nbi_calculado",
    "npbt_local",
]


def calcular_npbt_local(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula NPBT na visão LOCAL (econômica)."""
    df = df.copy()

    # Garante que colunas existam (preenche 0 se ausente)
    for col in ["sinistros_calculado", "comissao_calculada",
                "gastos_calculado", "other_nbi_calculado"]:
        if col not in df.columns:
            df[col] = 0.0

    # Protection: receita = premio_ganho_calculado
    # Savings:    receita = taf_calculado + carregamento_calculado  (premio_ganho = 0)
    df["npbt_local"] = (
        df.get("premio_ganho_calculado", 0)
        + df.get("taf_calculado", 0)
        + df.get("carregamento_calculado", 0)
        - df.get("sinistros_calculado", 0)
        - df.get("comissao_calculada", 0)
        - df.get("gastos_calculado", 0)
        - df.get("other_nbi_calculado", 0)
    )

    return df


def consolidar_resultado(
    df: pd.DataFrame,
    visao: str = "LOCAL",
    taxa_desconto_ifrs: float = 0.0,
    percentual_ra: float = 0.05,
    usar_paa: bool = True,
    variaveis_custom: list = None
) -> pd.DataFrame:
    """
    Pipeline final:
    1. Calcula NPBT local
    2. Aplica variáveis custom se houver
    3. Aplica IFRS17 se solicitado
    4. Agrupa e retorna resultado consolidado
    """
    from engine.variaveis_custom import aplicar_variaveis_custom

    df = calcular_npbt_local(df)

    # Variáveis custom
    if variaveis_custom:
        df = aplicar_variaveis_custom(df, variaveis_custom)

    if visao == "IFRS17":
        df = aplicar_ifrs17(df, usar_paa=usar_paa,
                            taxa_desconto=taxa_desconto_ifrs,
                            percentual_ra=percentual_ra)
        df["visao"] = "IFRS17"
    else:
        df["visao"] = "LOCAL"

    return df


def agrupar_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa por chaves analíticas e soma valores.
    Retorna DataFrame pronto para exportar.
    """
    # Identifica colunas numéricas
    colunas_numericas = df.select_dtypes(include=[np.number]).columns.tolist()

    # Garante que colunas chave existam
    chaves = [c for c in COLUNAS_CHAVE if c in df.columns]
    if "visao" in df.columns:
        chaves.append("visao")

    resultado = df.groupby(chaves, dropna=False)[colunas_numericas].sum().reset_index()
    return resultado


def exportar_csv(df: pd.DataFrame, filepath: str):
    """Exporta resultado final para CSV."""
    df_agrupado = agrupar_output(df)
    df_agrupado.to_csv(filepath, sep=";", decimal=",",
                       index=False, encoding="utf-8-sig")
    print(f"Output exportado: {filepath} ({len(df_agrupado)} linhas)")
    return df_agrupado


def gerar_resumo(df: pd.DataFrame) -> pd.DataFrame:
    """Gera resumo por produto e mês para exibição no painel."""
    chaves = [c for c in ["mes_projecao", "produto_atuarial", "businessline", "visao"]
              if c in df.columns]
    cols_resumo = [c for c in ["premio_ganho_calculado", "sinistros_calculado",
                                "comissao_calculada", "gastos_calculado",
                                "other_nbi_calculado", "npbt_local", "npbt_ifrs17"]
                   if c in df.columns]
    return df.groupby(chaves, dropna=False)[cols_resumo].sum().reset_index()
