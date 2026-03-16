"""
Engine de Persistência — Curvas de Cancelamento por Produto
Aplica curvas de sobrevivência mês a mês sobre Stock e New Business.

Lógica geral:
  - Curva: {produto: {mes_vida: pct}} ex: {0: 1.0, 1: 0.97, ..., 16: 0.0}
  - Mês de vida = datediff(data_inicio_vigencia, data_fim_mes_projetado) em meses completos
  - Fator mensal = persistencia[mes+1] / persistencia[mes]
  - Base do cálculo: quantidade_certificados × ticket_médio de cada indicador
  - PM cancela: libera tudo (prêmio emitido, comissão, sinistros, gastos)
  - PU cancela: libera APENAS a PPNG restante (meses futuros), não o prêmio já ganho
  - Prêmio ganho no mês do cancelamento: proporcional aos dias decorridos até o cancelamento
"""
import pandas as pd
import numpy as np
from pathlib import Path


# ─────────────────────────────────────────────────────
# Carregar curvas de persistência do Excel
# ─────────────────────────────────────────────────────

def carregar_persistencia_excel(filepath: str) -> dict:
    """
    Lê o Excel de persistência.
    Estrutura esperada: uma aba por produto OU colunas:
        produto_atuarial | mes_vida | persistencia

    Retorna dict: {produto_atuarial: {mes_vida: pct_persistencia}}
    Exemplo: {1001: {0: 1.0, 1: 0.97, 2: 0.95, ..., 24: 0.0}}
    """
    try:
        # Tenta ler como tabela flat (formato preferido)
        df = pd.read_excel(filepath, sheet_name=0)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        if "produto_atuarial" in df.columns and "mes_vida" in df.columns and "persistencia" in df.columns:
            return _df_para_dict(df)

        # Tenta formato wide: produto_atuarial | 0 | 1 | 2 | ... | 120
        elif "produto_atuarial" in df.columns:
            return _df_wide_para_dict(df)

        # Tenta múltiplas abas: cada aba = um produto
        else:
            xls = pd.ExcelFile(filepath)
            resultado = {}
            for sheet in xls.sheet_names:
                try:
                    produto_id = int(sheet)
                    df_aba = pd.read_excel(filepath, sheet_name=sheet)
                    df_aba.columns = [c.strip().lower().replace(" ", "_") for c in df_aba.columns]
                    if "mes_vida" in df_aba.columns and "persistencia" in df_aba.columns:
                        resultado[produto_id] = dict(zip(
                            df_aba["mes_vida"].astype(int),
                            df_aba["persistencia"].astype(float)
                        ))
                except (ValueError, KeyError):
                    continue
            return resultado

    except Exception as e:
        raise ValueError(f"Erro ao carregar persistência: {e}")


def _df_para_dict(df: pd.DataFrame) -> dict:
    """Converte DataFrame flat para dict de persistência."""
    resultado = {}
    for prod, grupo in df.groupby("produto_atuarial"):
        resultado[int(prod)] = dict(zip(
            grupo["mes_vida"].astype(int),
            grupo["persistencia"].astype(float)
        ))
    return resultado


def _df_wide_para_dict(df: pd.DataFrame) -> dict:
    """Converte DataFrame wide (colunas = mês) para dict."""
    resultado = {}
    for _, row in df.iterrows():
        produto = int(row["produto_atuarial"])
        curva = {}
        for col in df.columns:
            if col == "produto_atuarial":
                continue
            try:
                mes = int(col)
                curva[mes] = float(row[col])
            except (ValueError, TypeError):
                continue
        resultado[produto] = curva
    return resultado


def persistencia_padrao(n_meses: int = 24, pct_inicial: float = 1.0,
                         decaimento_mensal: float = 0.02) -> dict:
    """
    Gera curva de persistência padrão com decaimento linear.
    Útil como fallback quando produto não tem curva definida.
    """
    curva = {}
    for m in range(n_meses + 1):
        val = max(0.0, pct_inicial - m * decaimento_mensal)
        curva[m] = round(val, 6)
        if val <= 0:
            break
    return curva



# ─────────────────────────────────────────────────────
# Calcular mês de vida
# ─────────────────────────────────────────────────────

def calcular_mes_vida(data_inicio_vigencia, data_fim_mes_projetado) -> int:
    """
    Mês de vida = datediff(data_inicio_vigencia, data_fim_mes_projetado) em meses completos.
    Exemplo:
      ini_vig = 01/jan/2025, fim_mes = 31/jan/2025 → mes_vida = 0 (mesmo mês)
      ini_vig = 01/jan/2025, fim_mes = 28/fev/2025 → mes_vida = 1
      ini_vig = 01/jan/2025, fim_mes = 31/jan/2026 → mes_vida = 12
    """
    if pd.isnull(data_inicio_vigencia) or pd.isnull(data_fim_mes_projetado):
        return 0
    d_ini = pd.Timestamp(data_inicio_vigencia)
    d_fim = pd.Timestamp(data_fim_mes_projetado)
    meses = (d_fim.year - d_ini.year) * 12 + (d_fim.month - d_ini.month)
    return max(0, meses)


# ─────────────────────────────────────────────────────
# Fator de persistência mês a mês
# ─────────────────────────────────────────────────────

def fator_persistencia(curva: dict, mes_vida_atual: int) -> float:
    """
    Fator de transição: persistencia[mes+1] / persistencia[mes].
    Retorna 0.0 se cancelado ou fim da curva.
    """
    p_atual = curva.get(mes_vida_atual, None)
    p_prox  = curva.get(mes_vida_atual + 1, None)
    if p_atual is None or p_atual <= 0:
        return 0.0
    if p_prox is None:
        return 0.0
    return p_prox / p_atual


def persistencia_absoluta(curva: dict, mes_vida: int) -> float:
    return curva.get(mes_vida, 0.0)


# ─────────────────────────────────────────────────────
# Aplicar persistência acumulada com ticket médio
# ─────────────────────────────────────────────────────

# Colunas monetárias que escalam via ticket médio
COLUNAS_MONETARIAS = [
    "valor_premio_emitido",
    "valor_comissao",
    "comissao_calculada",
    "sinistros_calculado",
    "gastos_calculado",
    "other_nbi_calculado",
    "montante_capital",   # Savings: capital reduz conforme clientes saem
]

# Colunas PU-specific: só libera quando PU cancela (PPNG = reserva futura)
COLUNAS_PPNG = ["ppng_calculado", "valor_ppng"]

# Colunas de prêmio ganho: tratamento especial (proporcional a dias)
COLUNAS_PREMIO_GANHO = ["premio_ganho_calculado", "valor_premio_ganho_mes"]


def aplicar_persistencia_acumulada(
    df_base: pd.DataFrame,
    curvas: dict,
    produto_col: str = "produto_atuarial",
    fallback_curva: dict = None,
) -> pd.DataFrame:
    """
    Aplica persistência com lógica correta de ticket médio e PM vs PU.

    Para cada linha:
      1. Calcula mes_vida = datediff(data_inicio_vigencia, data_fim_mes) em meses
      2. Busca persistência absoluta para esse mes_vida → fator = P(mes) / P(0)
      3. Qtd certificados ativos = qtd_original × fator
      4. Certificados cancelados no mês = qtd × (fator_mes - fator_mes+1)
      5. Ticket médio de cada coluna = valor / qtd_original
      6. PM: ajusta TUDO pelo fator (certificados ativos)
         PU: ajusta prêmio emitido e PPNG pelo fator (libera reserva dos cancelados)
             prêmio ganho PM: já é mensal, ajusta pelo fator
             prêmio ganho PU: proporcional aos dias decorridos no mês × certificados ativos
      7. Prêmio ganho no mês do cancelamento: × (dias_decorridos / dias_no_mes)
      8. Remove linhas onde persistência == 0
    """
    df = df_base.copy()

    # Normaliza datas
    for col in ["data_inicio_vigencia", "data_ini_primeira_vigencia",
                "data_ini_mes", "data_fim_mes"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    qtd_col = "quantidade_certificados"

    def processar_linha(row):
        produto   = int(row.get(produto_col, 0))
        curva     = curvas.get(produto, fallback_curva or {})
        tipo_prem = str(row.get("tipo_premio", "PM")).upper()

        # data_ini_primeira_vigencia é a âncora fixa da posição na curva —
        # não reseta nas renovações. Fallback para data_inicio_vigencia se não existir.
        d_ini_primeira = row.get("data_ini_primeira_vigencia")
        d_ini_vig = d_ini_primeira if pd.notna(d_ini_primeira) else row.get("data_inicio_vigencia")
        d_fim_mes = row.get("data_fim_mes")
        d_ini_mes = row.get("data_ini_mes")

        # Sem curva = sem cancelamento
        if not curva:
            return row

        mes_vida = calcular_mes_vida(d_ini_vig, d_fim_mes)

        p0   = curva.get(0, 1.0)
        p_m  = curva.get(mes_vida, 0.0)
        p_m1 = curva.get(mes_vida + 1, 0.0)

        if p0 <= 0 or p_m <= 0:
            # Certificado já cancelado
            row = row.copy()
            row[qtd_col] = 0.0
            for c in COLUNAS_MONETARIAS + COLUNAS_PPNG + COLUNAS_PREMIO_GANHO:
                if c in row.index:
                    row[c] = 0.0
            row["fator_persistencia"] = 0.0
            row["mes_vida"] = mes_vida
            return row

        fator_abs    = p_m / p0          # % do volume original ainda ativo
        fator_prox   = p_m1 / p0 if p_m1 > 0 else 0.0
        fator_cancel = fator_abs - fator_prox   # % que cancela neste mês

        row = row.copy()
        qtd_orig = row.get(qtd_col, 1.0)
        if qtd_orig <= 0:
            qtd_orig = 1.0

        # ── Dias proporcionais para prêmio ganho no mês de cancelamento ──
        # Se há cancelamento neste mês, o prêmio ganho dos que cancelam é proporcional
        dias_no_mes  = (d_fim_mes - d_ini_mes).days + 1 if (d_ini_mes and d_fim_mes) else 30
        dias_decorr  = row.get("duration_decorrido_mes", dias_no_mes)
        fator_dias   = min(dias_decorr / dias_no_mes, 1.0) if dias_no_mes > 0 else 1.0

        # ── Ticket médio ──
        tickets = {}
        for c in COLUNAS_MONETARIAS + COLUNAS_PPNG + COLUNAS_PREMIO_GANHO:
            if c in row.index:
                tickets[c] = row[c] / qtd_orig

        # ── Quantidade ativa ──
        row[qtd_col] = qtd_orig * fator_abs

        # ── Colunas monetárias (mesma lógica PM e PU) ──
        for c in COLUNAS_MONETARIAS:
            if c in row.index:
                row[c] = tickets[c] * qtd_orig * fator_abs

        # ── PPNG: só existe em PU ──
        # PU cancela → libera PPNG dos cancelados (meses futuros)
        # Certificados que permanecem mantêm sua PPNG normal
        for c in COLUNAS_PPNG:
            if c in row.index:
                if tipo_prem == "PU":
                    # PPNG dos ativos (que ficam)
                    row[c] = tickets[c] * qtd_orig * fator_abs
                else:
                    row[c] = 0.0  # PM não tem PPNG

        # ── Prêmio ganho ──
        for c in COLUNAS_PREMIO_GANHO:
            if c in row.index:
                if tipo_prem == "PM":
                    # PM: prêmio ganho = emitido × fator (os ativos ganham tudo)
                    row[c] = tickets[c] * qtd_orig * fator_abs
                else:
                    # PU: prêmio ganho = proporcional aos dias
                    # Certificados ativos ganham normalmente
                    # Certificados que cancelam ganham só os dias que ficaram
                    ganho_ativos    = tickets[c] * qtd_orig * fator_prox
                    ganho_cancelados = tickets[c] * qtd_orig * fator_cancel * fator_dias
                    row[c] = ganho_ativos + ganho_cancelados

        row["fator_persistencia"] = fator_abs
        row["mes_vida"] = mes_vida
        return row

    df = df.apply(processar_linha, axis=1)

    # Remove linhas totalmente canceladas
    if "fator_persistencia" in df.columns:
        df = df[df["fator_persistencia"] > 0].copy()
    elif qtd_col in df.columns:
        df = df[df[qtd_col] > 0].copy()

    return df



# ─────────────────────────────────────────────────────
# Gerar Excel template de persistência
# ─────────────────────────────────────────────────────

def gerar_template_persistencia(produtos: list, n_meses: int = 24,
                                  filepath: str = "persistencia_template.xlsx"):
    """
    Gera um Excel template de persistência com curvas de exemplo.
    O usuário preenche os valores reais e faz upload.
    """
    rows = []
    for prod in produtos:
        for m in range(n_meses + 1):
            # Curva de exemplo com decaimento suave
            pct = max(0.0, round(1.0 - m * (1.0 / n_meses), 4))
            rows.append({
                "produto_atuarial": prod,
                "mes_vida": m,
                "persistencia": pct
            })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Persistencia")

        # Instrucoes
        pd.DataFrame({
            "Instrucoes": [
                "Preencha uma linha por produto por mês de vida (0 até o máximo desejado).",
                "mes_vida: 0 = mês de emissão, 1 = primeiro mês após emissão, etc.",
                "persistencia: valor entre 0 e 1 (ex: 0.97 = 97% ainda ativos).",
                "Quando persistencia = 0, o certificado é cancelado e não projetado mais.",
                "A curva pode ir até 120 meses.",
                "Produtos sem curva definida usarão o fallback padrão configurado no painel.",
            ]
        }).to_excel(writer, index=False, sheet_name="Instrucoes")

    print(f"Template gerado: {filepath}")
    return filepath
