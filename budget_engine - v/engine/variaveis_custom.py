"""
Variáveis Custom - Motor de execução de nós e fórmulas definidas pelo usuário
Suporta: node-based (nós conectados via drag&drop) e fórmula livre
"""
import pandas as pd
import numpy as np
import json
from typing import Any


# Colunas disponíveis como variáveis nas fórmulas
VARIAVEIS_DISPONIVEIS = [
    "valor_premio_emitido",
    "premio_ganho_calculado",
    "ppng_calculado",
    "sinistros_calculado",
    "comissao_calculada",
    "gastos_calculado",
    "other_nbi_calculado",
    "quantidade_certificados",
    "duration",
    "duration_decorrido",
    "duration_decorrido_mes",
    "npbt_local",
]


# ─────────────────────────────────────────────────────
# Tipos de nós disponíveis no node editor
# ─────────────────────────────────────────────────────

NOS_PREDEFINIDOS = {
    "input_coluna": {
        "label": "Coluna de Dados",
        "descricao": "Seleciona uma coluna existente como entrada",
        "parametros": {"coluna": "string"},
        "saida": "series"
    },
    "constante": {
        "label": "Constante",
        "descricao": "Valor numérico fixo",
        "parametros": {"valor": "float"},
        "saida": "float"
    },
    "operacao": {
        "label": "Operação",
        "descricao": "Operação entre duas entradas",
        "parametros": {"operador": ["soma", "subtracao", "multiplicacao", "divisao"]},
        "entradas": 2,
        "saida": "series"
    },
    "percentual": {
        "label": "Percentual",
        "descricao": "Aplica % sobre entrada",
        "parametros": {"percentual": "float"},
        "entradas": 1,
        "saida": "series"
    },
    "condicional": {
        "label": "Condicional (Se/Então)",
        "descricao": "Se coluna == valor então A senão B",
        "parametros": {"coluna_condicao": "string", "valor_condicao": "string",
                       "valor_verdadeiro": "float", "valor_falso": "float"},
        "saida": "series"
    },
    "formula_livre": {
        "label": "Fórmula Livre",
        "descricao": "Expressão Python personalizada",
        "parametros": {"formula": "string"},
        "saida": "series"
    },
    "saida_variavel": {
        "label": "Saída (Nova Variável)",
        "descricao": "Define o nome da variável resultante",
        "parametros": {"nome_variavel": "string", "afeta_npbt": "bool",
                       "sinal": ["positivo", "negativo"]},
        "entradas": 1,
        "saida": "coluna"
    }
}


# ─────────────────────────────────────────────────────
# Executor de grafo de nós
# ─────────────────────────────────────────────────────

class ExecutorNos:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.cache = {}

    def executar_no(self, no: dict) -> Any:
        """Executa um nó e retorna o resultado."""
        tipo = no["tipo"]
        params = no.get("parametros", {})
        no_id = no.get("id", tipo)

        if no_id in self.cache:
            return self.cache[no_id]

        resultado = None

        if tipo == "input_coluna":
            col = params.get("coluna", "")
            resultado = self.df.get(col, pd.Series(0, index=self.df.index))

        elif tipo == "constante":
            resultado = float(params.get("valor", 0))

        elif tipo == "percentual":
            entrada = self._resolver_entrada(no.get("entradas", []))
            pct = float(params.get("percentual", 0))
            resultado = entrada * pct

        elif tipo == "operacao":
            entradas = [self._resolver_entrada([e]) for e in no.get("entradas", [])]
            op = params.get("operador", "soma")
            if len(entradas) >= 2:
                a, b = entradas[0], entradas[1]
                if op == "soma":
                    resultado = a + b
                elif op == "subtracao":
                    resultado = a - b
                elif op == "multiplicacao":
                    resultado = a * b
                elif op == "divisao":
                    resultado = a / b.replace(0, np.nan)
            else:
                resultado = entradas[0] if entradas else pd.Series(0, index=self.df.index)

        elif tipo == "condicional":
            col_cond = params.get("coluna_condicao", "")
            val_cond = params.get("valor_condicao", "")
            val_true = float(params.get("valor_verdadeiro", 0))
            val_false = float(params.get("valor_falso", 0))
            col = self.df.get(col_cond, pd.Series("", index=self.df.index))
            resultado = np.where(col.astype(str) == str(val_cond), val_true, val_false)
            resultado = pd.Series(resultado, index=self.df.index)

        elif tipo == "formula_livre":
            formula = params.get("formula", "0")
            resultado = self._avaliar_formula(formula)

        self.cache[no_id] = resultado
        return resultado

    def _resolver_entrada(self, entradas: list) -> Any:
        if not entradas:
            return pd.Series(0, index=self.df.index)
        return self.executar_no(entradas[0])

    def _avaliar_formula(self, formula: str) -> pd.Series:
        """Avalia fórmula livre com acesso às colunas do DataFrame."""
        contexto = {col: self.df[col] for col in self.df.columns if col in VARIAVEIS_DISPONIVEIS}
        contexto["np"] = np
        contexto["pd"] = pd
        try:
            resultado = eval(formula, {"__builtins__": {}}, contexto)
            return pd.Series(resultado, index=self.df.index)
        except Exception as e:
            print(f"Erro na fórmula '{formula}': {e}")
            return pd.Series(0, index=self.df.index)


def aplicar_variaveis_custom(df: pd.DataFrame, nos_config: list) -> pd.DataFrame:
    """
    Aplica todas as variáveis custom definidas pelo usuário.
    nos_config: lista de grafos de nós (cada grafo = uma variável custom)
    """
    df = df.copy()
    executor = ExecutorNos(df)

    for grafo in nos_config:
        # Encontra o nó de saída
        no_saida = next((n for n in grafo if n["tipo"] == "saida_variavel"), None)
        if not no_saida:
            continue

        nome = no_saida["parametros"].get("nome_variavel", "custom_var")
        sinal = no_saida["parametros"].get("sinal", "negativo")
        afeta_npbt = no_saida["parametros"].get("afeta_npbt", True)

        # Executa o nó de entrada conectado ao de saída
        entradas = no_saida.get("entradas", [])
        if entradas:
            resultado = executor._resolver_entrada(entradas)
        else:
            resultado = pd.Series(0, index=df.index)

        df[nome] = resultado

        # Atualiza NPBT local se necessário
        if afeta_npbt and "npbt_local" in df.columns:
            if sinal == "negativo":
                df["npbt_local"] -= df[nome]
            else:
                df["npbt_local"] += df[nome]

    return df


def carregar_nos_de_json(filepath: str) -> list:
    """Carrega configuração de nós salva em JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_nos_em_json(nos_config: list, filepath: str):
    """Salva configuração de nós em JSON."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(nos_config, f, ensure_ascii=False, indent=2)
