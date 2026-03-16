"""
Engine IFRS17
Blocos: CSM, RA (Risk Adjustment), LIC/LRC, PAA
Recebe o DataFrame já calculado (visão LOCAL) e aplica ajustes IFRS17
"""
import pandas as pd
import numpy as np


# ─────────────────────────────────────────────────────
# PAA - Premium Allocation Approach
# Simplificação permitida para contratos <= 1 ano
# ─────────────────────────────────────────────────────

def aplicar_paa(df: pd.DataFrame) -> pd.DataFrame:
    """
    No PAA o prêmio é reconhecido linearmente ao longo da cobertura.
    Para PM: igual ao local (já é mensal).
    Para PU: idêntico ao cálculo de prêmio ganho proporcional já feito.
    O LRC (Liability for Remaining Coverage) = PPNG no contexto simplificado.
    """
    df = df.copy()
    df["ifrs17_lrc"] = df.get("ppng_calculado", 0)
    df["ifrs17_lic"] = df.get("sinistros_calculado", 0)  # LIC = sinistros incorridos
    df["ifrs17_revenue"] = df.get("premio_ganho_calculado", 0)
    return df


# ─────────────────────────────────────────────────────
# CSM - Contractual Service Margin
# Lucro não ganho reconhecido ao longo do serviço
# ─────────────────────────────────────────────────────

def calcular_csm(df: pd.DataFrame, taxa_desconto: float = 0.0) -> pd.DataFrame:
    """
    CSM inicial = PV(fluxos futuros esperados de saída) - PV(prêmios futuros)
    Simplificação: CSM = prêmio ganho - sinistros - comissão - gastos (margem esperada)
    Amortizado linearmente ao longo da cobertura.
    taxa_desconto: taxa anual para ajuste a valor presente (opcional)
    """
    df = df.copy()

    # Margem de serviço bruta
    df["ifrs17_csm_bruto"] = (
        df.get("premio_ganho_calculado", 0)
        - df.get("sinistros_calculado", 0)
        - df.get("comissao_calculada", 0)
        - df.get("gastos_calculado", 0)
        - df.get("other_nbi_calculado", 0)
    )

    # Ajuste a valor presente se taxa fornecida
    if taxa_desconto > 0:
        df["ifrs17_csm_bruto"] = df["ifrs17_csm_bruto"] / (1 + taxa_desconto / 12)

    # CSM amortizado no mês = CSM / duration restante
    def amortizar(row):
        dur_restante = row.get("duration", 1) - row.get("duration_decorrido", 0)
        dur_mes = row.get("duration_decorrido_mes", 30)
        if dur_restante <= 0:
            return row["ifrs17_csm_bruto"]
        return row["ifrs17_csm_bruto"] * (dur_mes / max(dur_restante, 1))

    df["ifrs17_csm_amortizado"] = df.apply(amortizar, axis=1)
    return df


# ─────────────────────────────────────────────────────
# RA - Risk Adjustment
# Compensação pela incerteza dos fluxos não-financeiros
# ─────────────────────────────────────────────────────

def calcular_ra(df: pd.DataFrame, percentual_ra: float = 0.05) -> pd.DataFrame:
    """
    RA = % aplicado sobre o prêmio ganho ou sobre a variância esperada de sinistros.
    Por padrão: RA = percentual_ra * premio_ganho_calculado
    percentual_ra: configurável por produto via hipóteses
    """
    df = df.copy()
    df["ifrs17_ra"] = df.get("premio_ganho_calculado", 0) * percentual_ra
    return df


# ─────────────────────────────────────────────────────
# LIC / LRC
# ─────────────────────────────────────────────────────

def calcular_lic_lrc(df: pd.DataFrame) -> pd.DataFrame:
    """
    LRC (Liability for Remaining Coverage): obrigação de cobertura futura
    LIC (Liability for Incurred Claims): sinistros ocorridos ainda não pagos
    """
    df = df.copy()
    df["ifrs17_lrc"] = df.get("ppng_calculado", 0) + df.get("ifrs17_ra", 0)
    df["ifrs17_lic"] = df.get("sinistros_calculado", 0)
    return df


# ─────────────────────────────────────────────────────
# Pipeline IFRS17 completo
# ─────────────────────────────────────────────────────

def aplicar_ifrs17(
    df: pd.DataFrame,
    usar_paa: bool = True,
    taxa_desconto: float = 0.0,
    percentual_ra: float = 0.05
) -> pd.DataFrame:
    """
    Aplica todos os blocos IFRS17 ao DataFrame.
    Retorna o DataFrame com colunas ifrs17_* adicionadas.
    """
    df = df.copy()
    df["visao"] = "IFRS17"

    if usar_paa:
        df = aplicar_paa(df)
    else:
        df = calcular_lic_lrc(df)

    df = calcular_ra(df, percentual_ra)
    df = calcular_csm(df, taxa_desconto)

    # NPBT IFRS17
    df["npbt_ifrs17"] = (
        df.get("ifrs17_revenue", df.get("premio_ganho_calculado", 0))
        - df.get("sinistros_calculado", 0)
        - df.get("comissao_calculada", 0)
        - df.get("gastos_calculado", 0)
        - df.get("other_nbi_calculado", 0)
        + df.get("ifrs17_csm_amortizado", 0)
        - df.get("ifrs17_ra", 0)
    )

    return df
