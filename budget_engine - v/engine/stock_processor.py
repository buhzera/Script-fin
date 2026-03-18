"""
Stock Processor - Lê e processa a fotografia da carteira vigente
Expande cada registro mês a mês com renovação automática

Lógica de horizonte e renovação (Protection):
  - horizonte_por_produto define o PERÍODO DE RENOVAÇÃO por produto
  - Após data_fim_vigencia, o contrato renova por mais 'horizonte' meses
  - A curva de persistência (aplicada depois) controla o corte real
  - 'safra' e 'safra_venda' são sempre preservadas do valor original do CSV

Lógica Savings:
  - Sem duração fixa e sem renovação automática
  - montante_capital cresce a cada mês com aportes líquidos (aporte - carregamento)
  - Persistência reduz montante_capital e quantidade_certificados
  - premio_ganho_calculado = 0, ppng_calculado = 0

Lógica mes_vida_stock_base (para persistência):
  - Stock já vem com posição "net" — não é 100% original
  - mes_vida_stock_base = mês de vida do registro no primeiro mês da projeção
  - Persistência usa P(mes_vida) / P(mes_vida_stock_base) em vez de P(mes_vida) / P(0)
  - Isso garante que apenas o DELTA futuro de cancelamento seja aplicado
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from engine.premio import aplicar_premio
from engine.persistencia import calcular_mes_vida


COLUNAS_STOCK = [
    "fonte", "safra", "data_fim_mes", "data_ini_mes",
    "produto_atuarial", "businessline", "safra_venda", "categoria",
    "tipo_premio", "valor_premio_emitido", "valor_comissao",
    "data_inicio_vigencia", "data_fim_vigencia",
    "montante_capital", "quantidade_certificados"
]


def carregar_stock(filepath: str) -> pd.DataFrame:
    """Carrega e valida o arquivo de stock."""
    df = pd.read_csv(filepath, sep=";", decimal=",", encoding="utf-8")
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    for col in ["data_fim_mes", "data_ini_mes", "data_inicio_vigencia", "data_fim_vigencia"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    for col in ["valor_premio_emitido", "valor_comissao", "quantidade_certificados", "montante_capital"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Garante coluna categoria (default Protection para arquivos antigos)
    if "categoria" not in df.columns:
        df["categoria"] = "Protection"

    # Garante coluna montante_capital
    if "montante_capital" not in df.columns:
        df["montante_capital"] = 0.0

    # Normaliza tipo_premio: strip de espaços
    if "tipo_premio" in df.columns:
        df["tipo_premio"] = df["tipo_premio"].astype(str).str.strip()
        # Para Savings sem tipo_premio definido, padroniza para "savings"
        mask_sav = df["categoria"] == "Savings"
        mask_nan = df["tipo_premio"].isin(["nan", "NaN", "", "None"])
        df.loc[mask_sav & mask_nan, "tipo_premio"] = "savings"

    # duration derivado das datas de vigência (não vem mais do CSV) — Protection only
    mask_prot = df["categoria"] != "Savings"
    df["duration"] = 0
    if mask_prot.any():
        df.loc[mask_prot, "duration"] = (
            df.loc[mask_prot, "data_fim_vigencia"] - df.loc[mask_prot, "data_inicio_vigencia"]
        ).dt.days.fillna(0).astype(int)

    return df


def expandir_stock_mes_a_mes(
    df: pd.DataFrame,
    horizonte_por_produto: dict,
    mes_base: date,
    max_meses_total: int = 120,
    savings_params: dict = None,
    max_meses_savings: int = 120,
) -> pd.DataFrame:
    """
    Expande o stock mês a mês.

    Protection: renovação automática a cada 'horizonte' meses.
    Savings:    sem renovação, capital cresce com aportes líquidos mensais.

    Parâmetros:
      horizonte_por_produto : {produto_atuarial: n_meses} — período de renovação (Protection)
      mes_base              : data de início da projeção
      max_meses_total       : teto de meses para Protection
      savings_params        : {str(produto): {aporte_medio, carregamento_por_aporte, taf_anual_pct}}
      max_meses_savings     : teto de meses para Savings
    """
    registros = []
    mes_base_ts = pd.Timestamp(mes_base).replace(day=1)
    savings_params = savings_params or {}

    # Fim do primeiro mês de projeção (usado para calcular mes_vida_base do Stock)
    fim_mes_0 = (mes_base_ts + relativedelta(months=1)) - timedelta(days=1)

    for _, row in df.iterrows():
        categoria = str(row.get("categoria", "Protection")).strip()

        # ── SAVINGS ────────────────────────────────────────────────────────────
        if categoria == "Savings":
            produto = str(row.get("produto_atuarial", "default"))
            sp      = savings_params.get(produto, savings_params.get("default", {}))
            aporte_medio       = sp.get("aporte_medio", 0)
            carregamento       = sp.get("carregamento_por_aporte", 0)
            net_aporte_por_cert = aporte_medio - carregamento

            capital_inicial = float(row.get("montante_capital", 0))
            qtd_inicial     = float(row.get("quantidade_certificados", 0))
            safra_orig       = row.get("safra")
            safra_venda_orig = row.get("safra_venda")
            data_ini_vig     = row.get("data_inicio_vigencia")
            if pd.isnull(data_ini_vig):
                data_ini_vig = mes_base_ts
            else:
                data_ini_vig = pd.Timestamp(data_ini_vig)

            # mes_vida_stock_base para Savings
            mes_vida_base_sav = calcular_mes_vida(data_ini_vig, fim_mes_0)

            for m in range(max_meses_savings):
                mes_proj = mes_base_ts + relativedelta(months=m)
                ini_mes  = mes_proj.replace(day=1)
                fim_mes  = (ini_mes + relativedelta(months=1)) - timedelta(days=1)

                novo = row.copy()
                novo["data_ini_mes"]               = ini_mes
                novo["data_fim_mes"]               = fim_mes
                novo["mes_projecao"]               = mes_proj.strftime("%Y/%m")
                novo["fonte"]                      = "Stock"
                novo["data_inicio_vigencia"]       = data_ini_vig
                novo["data_ini_primeira_vigencia"] = data_ini_vig
                novo["movimento"]                  = "Inicial"
                novo["safra"]                      = safra_orig
                novo["safra_venda"]                = safra_venda_orig
                novo["duration"]                   = 0
                novo["duration_decorrido"]         = 0
                novo["duration_decorrido_mes"]     = 0
                # Capital acumula aportes líquidos mês a mês (antes da persistência)
                novo["montante_capital"] = capital_inicial + m * net_aporte_por_cert * qtd_inicial
                # Âncora para persistência: mês de vida no início da projeção
                novo["mes_vida_stock_base"] = mes_vida_base_sav

                registros.append(novo)

        # ── PROTECTION ─────────────────────────────────────────────────────────
        else:
            data_fim_vig_orig = row.get("data_fim_vigencia")
            data_ini_vig_orig = row.get("data_inicio_vigencia")

            produto   = row.get("produto_atuarial", "default")
            horizonte = horizonte_por_produto.get(
                str(produto), horizonte_por_produto.get("default", 12)
            )

            # Se data_fim_vigencia estiver nula, calcula a partir do mes_base e horizonte
            if pd.isnull(data_fim_vig_orig):
                cur_ini_vig = (
                    pd.Timestamp(data_ini_vig_orig)
                    if not pd.isnull(data_ini_vig_orig)
                    else mes_base_ts
                )
                cur_fim_vig = cur_ini_vig + relativedelta(months=horizonte) - timedelta(days=1)
            else:
                data_fim_vig_orig = pd.Timestamp(data_fim_vig_orig)
                cur_ini_vig = (
                    pd.Timestamp(data_ini_vig_orig)
                    if not pd.isnull(data_ini_vig_orig)
                    else mes_base_ts
                )
                cur_fim_vig = data_fim_vig_orig

            data_ini_primeira_vig = cur_ini_vig
            safra_orig       = row.get("safra")
            safra_venda_orig = row.get("safra_venda")
            is_renovacao = False

            # mes_vida_stock_base: mês de vida deste registro no primeiro mês de projeção
            mes_vida_base_prot = calcular_mes_vida(data_ini_primeira_vig, fim_mes_0)

            for m in range(max_meses_total):
                mes_proj = mes_base_ts + relativedelta(months=m)
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
                novo["fonte"]                      = "Stock"
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
                # Âncora para persistência: mês de vida no início da projeção
                novo["mes_vida_stock_base"] = mes_vida_base_prot

                registros.append(novo)

    if not registros:
        return pd.DataFrame()

    resultado = pd.DataFrame(registros)
    resultado = aplicar_premio(resultado)
    return resultado


def processar_stock(filepath: str, horizonte_por_produto: dict,
                    mes_base: date, max_meses_total: int = 120,
                    savings_params: dict = None,
                    max_meses_savings: int = 120) -> pd.DataFrame:
    """Pipeline completo: carrega → expande → calcula prêmio."""
    df = carregar_stock(filepath)
    return expandir_stock_mes_a_mes(
        df, horizonte_por_produto, mes_base,
        max_meses_total, savings_params, max_meses_savings
    )
