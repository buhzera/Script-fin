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
  - Persistência usa P(mes_vida) / P(mes_vida_stock_base - 1)
  - Isso garante que o cancelamento incremental seja aplicado desde o primeiro mês
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from engine.premio import aplicar_premio


COLUNAS_STOCK = [
    "fonte", "safra", "data_fim_mes", "data_ini_mes",
    "produto_atuarial", "businessline", "safra_venda", "categoria",
    "tipo_premio", "valor_premio_emitido", "valor_comissao",
    "data_inicio_vigencia", "data_fim_vigencia",
    "montante_capital", "quantidade_certificados"
]


# ─────────────────────────────────────────────────────
# Helpers de aritmética de datas vectorizada
# ─────────────────────────────────────────────────────

def _days_in_month(year_arr, month_arr):
    """Dias no mês — vectorizado, trata anos bissextos."""
    y = np.asarray(year_arr, dtype=int)
    m = np.asarray(month_arr, dtype=int)
    # Dias base (ano não-bissexto)
    base = np.array([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    d = base[m]
    is_leap = ((y % 4 == 0) & (y % 100 != 0)) | (y % 400 == 0)
    d = np.where((m == 2) & is_leap, 29, d)
    return d


def _mi_to_first(month_int):
    """Month integer (0-indexed) → primeiro dia do mês (DatetimeIndex)."""
    mi = np.asarray(month_int, dtype=int)
    y = mi // 12
    m = mi % 12 + 1
    return pd.to_datetime({"year": y, "month": m, "day": np.ones(len(mi), dtype=int)})


def _mi_to_last(month_int):
    """Month integer (0-indexed) → último dia do mês (DatetimeIndex)."""
    mi = np.asarray(month_int, dtype=int)
    y = mi // 12
    m = mi % 12 + 1
    d = _days_in_month(y, m)
    return pd.to_datetime({"year": y, "month": m, "day": d})


def _mi_day_to_date(month_int, day_arr):
    """Month integer + array de dias → datas (dia capado ao fim do mês)."""
    mi = np.asarray(month_int, dtype=int)
    y  = mi // 12
    m  = mi % 12 + 1
    max_d = _days_in_month(y, m)
    d = np.minimum(np.asarray(day_arr, dtype=int), max_d)
    return pd.to_datetime({"year": y, "month": m, "day": d})


def _mi_str(month_int):
    """Month integer → 'YYYY/MM' (array de strings)."""
    mi = np.asarray(month_int, dtype=int)
    y  = mi // 12
    m  = mi % 12 + 1
    return pd.array([f"{yi:04d}/{mi_:02d}" for yi, mi_ in zip(y, m)], dtype="object")


# ─────────────────────────────────────────────────────
# Carregar
# ─────────────────────────────────────────────────────

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

    if "categoria" not in df.columns:
        df["categoria"] = "Protection"

    if "montante_capital" not in df.columns:
        df["montante_capital"] = 0.0

    if "tipo_premio" in df.columns:
        df["tipo_premio"] = df["tipo_premio"].astype(str).str.strip()
        mask_sav = df["categoria"] == "Savings"
        mask_nan = df["tipo_premio"].isin(["nan", "NaN", "", "None"])
        df.loc[mask_sav & mask_nan, "tipo_premio"] = "savings"

    mask_prot = df["categoria"] != "Savings"
    df["duration"] = 0
    if mask_prot.any():
        df.loc[mask_prot, "duration"] = (
            df.loc[mask_prot, "data_fim_vigencia"] - df.loc[mask_prot, "data_inicio_vigencia"]
        ).dt.days.fillna(0).astype(int)

    return df


# ─────────────────────────────────────────────────────
# Expandir — vectorizado
# ─────────────────────────────────────────────────────

def expandir_stock_mes_a_mes(
    df: pd.DataFrame,
    horizonte_por_produto: dict,
    mes_base: date,
    max_meses_total: int = 120,
    savings_params: dict = None,
    max_meses_savings: int = 120,
) -> pd.DataFrame:
    """
    Expande o stock mês a mês (implementação vetorizada — muito mais rápida).

    Protection: renovação automática a cada 'horizonte' meses.
    Savings:    sem renovação, capital cresce com aportes líquidos mensais.
    """
    mes_base_ts = pd.Timestamp(mes_base).replace(day=1)
    savings_params = savings_params or {}

    # mes_vida_stock_base usa o fim do 1º mês de projeção como referência
    fim_mes_0_ts = (mes_base_ts + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
    fim_mes_0_mi = fim_mes_0_ts.year * 12 + fim_mes_0_ts.month - 1  # 0-indexed

    cat_col = (
        df["categoria"].astype(str).str.strip()
        if "categoria" in df.columns
        else pd.Series("Protection", index=df.index)
    )
    mask_sav = (cat_col == "Savings").values

    frames = []

    # ══════════════════════════════════════════════════
    # SAVINGS
    # ══════════════════════════════════════════════════
    df_sav = df[mask_sav].copy().reset_index(drop=True)
    if not df_sav.empty:
        n   = len(df_sav)
        n_m = max_meses_savings
        ri    = np.repeat(np.arange(n), n_m)
        m_arr = np.tile(np.arange(n_m), n)

        d_ini = (
            pd.to_datetime(df_sav["data_inicio_vigencia"], errors="coerce")
            .fillna(mes_base_ts)
        )

        # mes_vida_stock_base
        ini_mi = d_ini.dt.year.values * 12 + d_ini.dt.month.values - 1
        mv_base = np.maximum(0, fim_mes_0_mi - ini_mi)

        base_mi = mes_base_ts.year * 12 + mes_base_ts.month - 1
        proj_mi = base_mi + m_arr

        dfe = df_sav.iloc[ri].reset_index(drop=True)
        dfe["data_ini_mes"]               = _mi_to_first(proj_mi).values
        dfe["data_fim_mes"]               = _mi_to_last(proj_mi).values
        dfe["mes_projecao"]               = _mi_str(proj_mi)
        dfe["fonte"]                      = "Stock"
        dfe["data_inicio_vigencia"]       = d_ini.values[ri]
        dfe["data_ini_primeira_vigencia"] = d_ini.values[ri]
        dfe["movimento"]                  = "Inicial"
        dfe["duration"]                   = 0
        dfe["duration_decorrido"]         = 0
        dfe["duration_decorrido_mes"]     = 0
        dfe["mes_vida_stock_base"]        = mv_base[ri]

        # Capital acumula aportes
        prod_strs = df_sav["produto_atuarial"].astype(str).values
        net_ap = np.zeros(n)
        for i, p in enumerate(prod_strs):
            sp = savings_params.get(p, savings_params.get("default", {}))
            net_ap[i] = sp.get("aporte_medio", 0) - sp.get("carregamento_por_aporte", 0)

        qtd_ini = pd.to_numeric(df_sav["quantidade_certificados"], errors="coerce").fillna(0).values
        cap_ini = pd.to_numeric(df_sav["montante_capital"],        errors="coerce").fillna(0).values
        dfe["montante_capital"] = cap_ini[ri] + m_arr * net_ap[ri] * qtd_ini[ri]

        frames.append(dfe)

    # ══════════════════════════════════════════════════
    # PROTECTION
    # ══════════════════════════════════════════════════
    df_prot = df[~mask_sav].copy().reset_index(drop=True)
    if not df_prot.empty:
        n   = len(df_prot)
        n_m = max_meses_total
        ri    = np.repeat(np.arange(n), n_m)
        m_arr = np.tile(np.arange(n_m), n)

        # horizonte por produto (per row)
        prod_arr = df_prot["produto_atuarial"].astype(str).values
        hor_per_row = np.array([
            horizonte_por_produto.get(p, horizonte_por_produto.get("default", 12))
            for p in prod_arr
        ], dtype=int).clip(min=1)

        d_ini_raw = pd.to_datetime(df_prot["data_inicio_vigencia"], errors="coerce")
        d_fim_raw = pd.to_datetime(df_prot["data_fim_vigencia"],     errors="coerce")
        d_ini_fil = d_ini_raw.fillna(mes_base_ts)

        # Preenche data_fim_vigencia nula: ini + H months - 1 day
        d_fim = d_fim_raw.copy()
        null_fim = d_fim_raw.isna().values
        if null_fim.any():
            ini_null = d_ini_fil.values[null_fim]
            ini_null_ts = pd.Series(ini_null)
            hor_null = hor_per_row[null_fim]
            ini_mi_null = ini_null_ts.dt.year.values * 12 + ini_null_ts.dt.month.values - 1
            fim_mi_null = ini_mi_null + hor_null
            max_d_null = _days_in_month(fim_mi_null // 12, fim_mi_null % 12 + 1)
            fim_day_null = np.minimum(ini_null_ts.dt.day.values, max_d_null)
            computed = (
                pd.to_datetime({"year": fim_mi_null // 12, "month": fim_mi_null % 12 + 1, "day": fim_day_null})
                - pd.Timedelta(days=1)
            )
            d_fim_arr = d_fim.values.copy()
            d_fim_arr[null_fim] = computed.values
            d_fim = pd.Series(d_fim_arr)

        d_fim_ts = pd.to_datetime(d_fim, errors="coerce")
        fim_vig_mi   = d_fim_ts.dt.year.values * 12 + d_fim_ts.dt.month.values - 1
        fim_vig_day  = d_fim_ts.dt.day.values

        # mes_vida_stock_base (per row)
        ini_mi_row = d_ini_fil.dt.year.values * 12 + d_ini_fil.dt.month.values - 1
        mv_base_row = np.maximum(0, fim_mes_0_mi - ini_mi_row)

        # Expande
        hor_exp       = hor_per_row[ri].clip(min=1)
        fim_vig_mi_e  = fim_vig_mi[ri]
        fim_vig_day_e = fim_vig_day[ri]
        d_ini_exp     = d_ini_fil.values[ri]
        mv_base_exp   = mv_base_row[ri]

        base_mi = mes_base_ts.year * 12 + mes_base_ts.month - 1
        proj_mi = base_mi + m_arr

        # Número de renovações k para cada (row, mês)
        months_over = proj_mi - fim_vig_mi_e
        k = np.where(months_over > 0, (months_over - 1) // hor_exp + 1, 0)

        # cur_fim_vig = data_fim_vigencia + k * H meses
        new_fim_mi  = fim_vig_mi_e + k * hor_exp
        cur_fim     = _mi_day_to_date(new_fim_mi, fim_vig_day_e)

        # cur_ini_vig (k > 0): fim anterior + 1 dia
        prev_fim_mi = fim_vig_mi_e + np.maximum(0, k - 1) * hor_exp
        prev_fim    = _mi_day_to_date(prev_fim_mi, fim_vig_day_e)
        cur_ini_renov = (prev_fim + pd.Timedelta(days=1)).values

        is_renov = k > 0
        cur_ini_final = d_ini_exp.copy()
        cur_ini_final[is_renov] = cur_ini_renov[is_renov]
        cur_fim_final = cur_fim.values

        ini_mes = _mi_to_first(proj_mi)
        fim_mes = _mi_to_last(proj_mi)

        cur_ini_pd = pd.to_datetime(pd.Series(cur_ini_final))
        cur_fim_pd = pd.to_datetime(pd.Series(cur_fim_final))
        ini_mes_pd = pd.to_datetime(pd.Series(ini_mes.values))
        fim_mes_pd = pd.to_datetime(pd.Series(fim_mes.values))

        dfe = df_prot.iloc[ri].reset_index(drop=True)
        dfe["data_ini_mes"]               = ini_mes.values
        dfe["data_fim_mes"]               = fim_mes.values
        dfe["mes_projecao"]               = _mi_str(proj_mi)
        dfe["fonte"]                      = "Stock"
        dfe["data_inicio_vigencia"]       = cur_ini_final
        dfe["data_fim_vigencia"]          = cur_fim_final
        dfe["data_ini_primeira_vigencia"] = d_ini_exp
        dfe["movimento"]                  = np.where(is_renov, "Renovação", "Inicial")
        dfe["mes_vida_stock_base"]        = mv_base_exp

        dfe["duration"] = (
            (cur_fim_pd - cur_ini_pd).dt.days.fillna(0).values.clip(min=0)
        )
        dfe["duration_decorrido"] = (
            (fim_mes_pd - cur_ini_pd).dt.days.fillna(0).values
        )
        days_proj   = (fim_mes_pd - ini_mes_pd + pd.Timedelta(days=1)).dt.days.values
        days_to_fim = ((cur_fim_pd - ini_mes_pd + pd.Timedelta(days=1)).dt.days.fillna(0).values).clip(min=0)
        dfe["duration_decorrido_mes"] = np.minimum(days_proj, days_to_fim)

        frames.append(dfe)

    if not frames:
        return pd.DataFrame()

    resultado = pd.concat(frames, ignore_index=True)
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
