"""
New Business Processor - Processa projeção manual de novas vendas
Gera registros mensais a partir das hipóteses de entrada de NB

Lógica Protection (horizonte e renovação):
  - horizonte_por_produto define o PERÍODO DE RENOVAÇÃO do produto (ex: 12 = renova anualmente)
  - A projeção vai até max_meses_total, renovando o contrato a cada 'horizonte' meses
  - A curva de persistência (aplicada depois) controla quando as apólices cancelam
  - 'safra' nunca é alterada — preservada sempre do valor original do CSV

Lógica Savings:
  - Sem renovação automática, sem duration fixa
  - montante_capital cresce a cada mês com aportes líquidos (aporte - carregamento)
  - Persistência reduz capital e certificados
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from engine.premio import aplicar_premio


def carregar_new_business(filepath: str) -> pd.DataFrame:
    """
    Carrega o arquivo de New Business.
    Cada linha representa vendas projetadas para um determinado mês/produto/safra.
    """
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    for col in ["data_fim_mes", "data_ini_mes", "data_inicio_vigencia", "data_fim_vigencia"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    for col in ["valor_premio_emitido", "valor_comissao", "quantidade_certificados", "montante_capital"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Garante coluna categoria
    if "categoria" not in df.columns:
        df["categoria"] = "Protection"

    # Garante coluna montante_capital
    if "montante_capital" not in df.columns:
        df["montante_capital"] = 0.0

    # Normaliza tipo_premio: strip de espaços; Savings sem tipo → "savings"
    if "tipo_premio" in df.columns:
        df["tipo_premio"] = df["tipo_premio"].astype(str).str.strip()
        mask_sav = df["categoria"] == "Savings"
        mask_nan = df["tipo_premio"].isin(["nan", "NaN", "", "None"])
        df.loc[mask_sav & mask_nan, "tipo_premio"] = "savings"

    # duration derivado das datas de vigência — Protection only
    df["duration"] = 0
    mask_prot = df["categoria"] != "Savings"
    if mask_prot.any():
        df.loc[mask_prot, "duration"] = (
            df.loc[mask_prot, "data_fim_vigencia"] - df.loc[mask_prot, "data_inicio_vigencia"]
        ).dt.days.fillna(0).astype(int)

    df["fonte"] = "New Business"
    return df


def expandir_nb_mes_a_mes(
    df: pd.DataFrame,
    horizonte_por_produto: dict,
    max_meses_total: int = 120,
    savings_params: dict = None,
    max_meses_savings: int = 120,
) -> pd.DataFrame:
    """
    Expande o NB mês a mês.

    Protection: renovação automática a cada 'horizonte' meses.
    Savings:    sem renovação, capital cresce com aportes líquidos mensais.

    Parâmetros:
      horizonte_por_produto : {produto_atuarial: n_meses} (Protection)
      max_meses_total       : teto de meses para Protection
      savings_params        : {str(produto): {aporte_medio, carregamento_por_aporte, taf_anual_pct}}
      max_meses_savings     : teto de meses para Savings
    """
    registros = []
    savings_params = savings_params or {}

    for _, row in df.iterrows():
        categoria = str(row.get("categoria", "Protection")).strip()

        # ── SAVINGS ────────────────────────────────────────────────────────────
        if categoria == "Savings":
            produto = str(row.get("produto_atuarial", "default"))
            sp      = savings_params.get(produto, savings_params.get("default", {}))
            aporte_medio        = sp.get("aporte_medio", 0)
            carregamento        = sp.get("carregamento_por_aporte", 0)
            net_aporte_por_cert = aporte_medio - carregamento

            data_ini_vig_orig = row.get("data_inicio_vigencia")
            if pd.isnull(data_ini_vig_orig):
                continue
            data_ini_vig_orig = pd.Timestamp(data_ini_vig_orig)
            mes_venda = data_ini_vig_orig.replace(day=1)

            capital_inicial = float(row.get("montante_capital", 0))
            qtd_inicial     = float(row.get("quantidade_certificados", 0))
            safra_orig       = row.get("safra")
            safra_venda_orig = row.get("safra_venda")

            for m in range(max_meses_savings):
                mes_proj = mes_venda + relativedelta(months=m)
                ini_mes  = mes_proj.replace(day=1)
                fim_mes  = (ini_mes + relativedelta(months=1)) - timedelta(days=1)

                novo = row.copy()
                novo["data_ini_mes"]               = ini_mes
                novo["data_fim_mes"]               = fim_mes
                novo["mes_projecao"]               = mes_proj.strftime("%Y/%m")
                novo["data_inicio_vigencia"]       = data_ini_vig_orig
                novo["data_ini_primeira_vigencia"] = data_ini_vig_orig
                novo["movimento"]                  = "Inicial"
                novo["safra"]                      = safra_orig
                novo["safra_venda"]                = safra_venda_orig
                novo["duration"]                   = 0
                novo["duration_decorrido"]         = 0
                novo["duration_decorrido_mes"]     = 0
                novo["montante_capital"] = capital_inicial + m * net_aporte_por_cert * qtd_inicial

                registros.append(novo)

        # ── PROTECTION ─────────────────────────────────────────────────────────
        else:
            produto = row.get("produto_atuarial")
            horizonte = horizonte_por_produto.get(
                str(produto), horizonte_por_produto.get("default", 12)
            )

            data_ini_vig_orig = row.get("data_inicio_vigencia")
            data_fim_vig_csv  = row.get("data_fim_vigencia")

            if pd.isnull(data_ini_vig_orig):
                continue

            data_ini_vig_orig = pd.Timestamp(data_ini_vig_orig)
            mes_venda = data_ini_vig_orig.replace(day=1)

            safra_orig       = row.get("safra")
            safra_venda_orig = row.get("safra_venda")
            data_ini_primeira_vig = data_ini_vig_orig

            if pd.isnull(data_fim_vig_csv):
                cur_fim_vig = data_ini_vig_orig + relativedelta(months=horizonte) - timedelta(days=1)
            else:
                cur_fim_vig = pd.Timestamp(data_fim_vig_csv)
            cur_ini_vig = data_ini_vig_orig
            is_renovacao = False

            for m in range(max_meses_total):
                mes_proj = mes_venda + relativedelta(months=m)
                ini_mes  = mes_proj.replace(day=1)
                fim_mes  = (ini_mes + relativedelta(months=1)) - timedelta(days=1)

                while cur_fim_vig < ini_mes:
                    cur_ini_vig  = cur_fim_vig + timedelta(days=1)
                    cur_fim_vig  = cur_ini_vig + relativedelta(months=horizonte) - timedelta(days=1)
                    is_renovacao = True

                novo = row.copy()
                novo["data_ini_mes"]               = ini_mes
                novo["data_fim_mes"]               = fim_mes
                novo["mes_projecao"]               = mes_proj.strftime("%Y/%m")
                novo["data_inicio_vigencia"]       = cur_ini_vig
                novo["data_fim_vigencia"]          = cur_fim_vig
                novo["data_ini_primeira_vigencia"] = data_ini_primeira_vig
                novo["movimento"]                  = "Renovação" if is_renovacao else "Inicial"
                novo["safra"]                      = safra_orig
                novo["safra_venda"]                = safra_venda_orig
                novo["duration"]                   = (cur_fim_vig - cur_ini_vig).days
                novo["duration_decorrido"]         = (fim_mes - cur_ini_vig).days
                novo["duration_decorrido_mes"]     = max(0, min(
                    (fim_mes - ini_mes).days + 1,
                    (cur_fim_vig - ini_mes).days + 1,
                ))

                registros.append(novo)

    if not registros:
        return pd.DataFrame()

    resultado = pd.DataFrame(registros)
    resultado = aplicar_premio(resultado)
    return resultado


def processar_nb(filepath: str, horizonte_por_produto: dict,
                 max_meses_total: int = 120,
                 savings_params: dict = None,
                 max_meses_savings: int = 120) -> pd.DataFrame:
    """Pipeline completo NB: carrega → expande → calcula prêmio."""
    df = carregar_new_business(filepath)
    return expandir_nb_mes_a_mes(
        df, horizonte_por_produto, max_meses_total,
        savings_params, max_meses_savings
    )
