# Budget Engine

Engine de cálculo de budget: Prêmio, Prêmio Ganho, Sinistros, Comissão, Gastos, Other NBI → NPBT.
Visões: **LOCAL** (econômica) e **IFRS17**.

---

## Estrutura do Projeto

```
budget_engine/
├── engine/
│   ├── premio.py              # Cálculo PM/PU, PPNG
│   ├── stock_processor.py     # Expansão do stock mês a mês
│   ├── nb_processor.py        # Expansão do new business
│   ├── sinistros.py           # Hipóteses de sinistralidade
│   ├── comissao_gastos.py     # Comissão e gastos variáveis
│   ├── variaveis_custom.py    # Node editor + fórmulas livres
│   ├── ifrs17.py              # CSM, RA, LIC/LRC, PAA
│   └── resultado.py           # NPBT e output CSV
├── inputs/
│   ├── stock.csv              # Fotografia da carteira
│   ├── new_business.csv       # Projeção de vendas
│   └── hipoteses/
│       ├── sinistros.csv
│       ├── comissao.csv
│       └── gastos.csv
├── output/
│   └── budget_output.csv
├── ui/
│   └── app.py                 # Painel Streamlit
├── requirements.txt
└── README.md
```

---

## Como Rodar

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Rodar o painel
```bash
# A partir da pasta budget_engine/
streamlit run ui/app.py
```

Ou no PyCharm: abrir terminal e rodar o comando acima.

---

## Inputs Esperados

### stock.csv / new_business.csv
Separador: `;` | Decimal: `,` | Encoding: UTF-8

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| fonte | STRING | Stock ou New Business |
| safra | STRING | AAAA/MM |
| data_fim_mes | DATE | DD/MM/AAAA |
| data_ini_mes | DATE | DD/MM/AAAA |
| produto_atuarial | INT | ex: 1234 |
| businessline | STRING | ex: Personal Protection |
| safra_venda | STRING | AAAA/MM |
| tipo_premio | STRING | PM ou PU |
| valor_premio_emitido | FLOAT | |
| valor_comissao | FLOAT | |
| valor_premio_ganho_mes | FLOAT | |
| valor_ppng | FLOAT | |
| data_inicio_vigencia | DATE | DD/MM/AAAA |
| data_fim_vigencia | DATE | DD/MM/AAAA |
| duration | INT | dias |
| duration_decorrido | INT | dias |
| duration_decorrido_mes | INT | dias no mês |
| quantidade_certificados | INT | |

### hipoteses/sinistros.csv
`produto_atuarial;businessline;tipo_hipotese;valor;frequencia;severidade_media`

`tipo_hipotese`: `percentual_premio_ganho` | `valor_fixo` | `frequencia_severidade`

### hipoteses/comissao.csv
`produto_atuarial;businessline;tipo_regra;valor`

`tipo_regra`: `percentual_premio_emitido` | `percentual_premio_ganho` | `valor_fixo`

### hipoteses/gastos.csv
`produto_atuarial;businessline;tipo_gasto;tipo_regra;valor`

`tipo_gasto`: `gastos` | `other_nbi` | `custom_*`

---

## Variáveis Custom

Na aba **Variáveis Custom** do painel você pode:

- **Node Builder**: montar visualmente entrada → operação → saída
- **Fórmula Livre**: escrever expressão Python usando as colunas disponíveis

Configurações são salváveis em JSON e recarregáveis.

---

## Output

CSV com separador `;`, decimal `,`, todas as linhas por:
`mes_projecao | fonte | produto_atuarial | businessline | safra_venda | tipo_premio | visao`

Colunas de resultado:
- `premio_ganho_calculado`
- `ppng_calculado`
- `sinistros_calculado`
- `comissao_calculada`
- `gastos_calculado`
- `other_nbi_calculado`
- `npbt_local`
- `npbt_ifrs17` (se visão IFRS17)
- `ifrs17_csm_amortizado`, `ifrs17_ra`, `ifrs17_lrc`, `ifrs17_lic`
