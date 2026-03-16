"""
Session Manager — Budget Engine
Modelo: Sessão (projeto mãe) → Versões (snapshots dentro da sessão)
Cada versão é um .zip autocontido.
"""
import os
import json
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
import pandas as pd

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
SESSION_INDEX = SESSIONS_DIR / "index.json"


# ─────────────────────────────────────────────────────
# Utilitários internos
# ─────────────────────────────────────────────────────

def _session_path(version_id: str) -> Path:
    return SESSIONS_DIR / f"{version_id}.zip"


def _load_index() -> list:
    if SESSION_INDEX.exists():
        with open(SESSION_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_index(index: list):
    with open(SESSION_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def _gerar_id(nome: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = nome.lower().replace(" ", "_").replace("/", "")[:20]
    return f"{slug}_{ts}"


def _sessao_raiz_id(entry: dict) -> str:
    """Retorna o ID raiz de uma entrada (compatibilidade com registros antigos)."""
    return entry.get("sessao_raiz_id") or entry["id"]


# ─────────────────────────────────────────────────────
# Listar Sessões (projetos mãe) — para o gate
# ─────────────────────────────────────────────────────

def listar_sessoes_raiz() -> list:
    """
    Retorna uma entrada por sessão (projeto mãe).
    Mostra o nome da sessão e a versão mais recente de cada uma.
    """
    index = _load_index()
    grupos: dict[str, dict] = {}
    for entry in index:
        raiz = _sessao_raiz_id(entry)
        if raiz not in grupos:
            grupos[raiz] = entry
        else:
            # Mantém a mais recente para exibição
            if entry.get("criado_em", "") > grupos[raiz].get("criado_em", ""):
                grupos[raiz] = {**entry, "sessao_raiz_id": raiz,
                                "nome_sessao": entry.get("nome_sessao", entry["nome"])}
    # Ordena por data da versão mais recente
    result = list(grupos.values())
    result.sort(key=lambda x: x.get("criado_em", ""), reverse=True)
    return result


def listar_sessoes_raiz_df() -> pd.DataFrame:
    """DataFrame com uma linha por sessão (para o gate)."""
    raizes = listar_sessoes_raiz()
    if not raizes:
        return pd.DataFrame()
    rows = []
    for r in raizes:
        raiz_id = _sessao_raiz_id(r)
        versoes = listar_versoes(raiz_id)
        rows.append({
            "sessao_raiz_id": raiz_id,
            "nome_sessao": r.get("nome_sessao") or r.get("nome", "—"),
            "autor": r.get("autor", ""),
            "criado_em": r.get("criado_em", "")[:16],
            "n_versoes": len(versoes),
            "ultima_versao": versoes[-1].get("nome_versao") or versoes[-1].get("nome", "—") if versoes else "—",
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────
# Listar Versões de uma sessão
# ─────────────────────────────────────────────────────

def listar_versoes(sessao_raiz_id: str) -> list:
    """Retorna todas as versões de uma sessão, ordenadas por data."""
    index = _load_index()
    versoes = [e for e in index if _sessao_raiz_id(e) == sessao_raiz_id]
    versoes.sort(key=lambda x: x.get("criado_em", ""))
    return versoes


def obter_ultima_versao_id(sessao_raiz_id: str) -> str | None:
    """Retorna o ID da versão mais recente de uma sessão."""
    versoes = listar_versoes(sessao_raiz_id)
    return versoes[-1]["id"] if versoes else None


def _proximo_num_versao(sessao_raiz_id: str) -> int:
    return len(listar_versoes(sessao_raiz_id)) + 1


# ─────────────────────────────────────────────────────
# Salvar versão
# ─────────────────────────────────────────────────────

def salvar_versao(
    # Identificação da sessão
    nome_sessao: str,
    nome_versao: str,
    descricao: str,
    autor: str,
    # sessao_raiz_id: None = nova sessão, str = versão dentro de sessão existente
    sessao_raiz_id: str = None,
    # Configurações globais
    mes_base: str = "",
    visao: str = "LOCAL",
    usar_paa: bool = True,
    taxa_desconto: float = 0.0,
    percentual_ra: float = 0.05,
    horizonte_por_produto: dict = None,
    max_meses_total: int = 120,
    pasta_fonte: str = "",
    # Hipóteses
    df_sinistros: pd.DataFrame = None,
    df_comissao: pd.DataFrame = None,
    df_gastos: pd.DataFrame = None,
    df_premissas_proj: pd.DataFrame = None,
    # Inputs binários
    stock_bytes: bytes = None,
    nb_bytes: bytes = None,
    # Variáveis custom
    nos_custom: list = None,
    # Se informado, sobrescreve essa versão (mesmo ID)
    version_id_fixo: str = None,
    # Fallbacks de hipóteses
    fallbacks: dict = None,
    df_fallback_curva: pd.DataFrame = None,
    df_fallback_curva_sav: pd.DataFrame = None,
) -> str:
    """
    Salva uma versão dentro de uma sessão.
    - sessao_raiz_id=None → cria nova sessão (V1 automática)
    - sessao_raiz_id=X    → cria nova versão dentro da sessão X
    - version_id_fixo=Y   → sobrescreve a versão Y no lugar
    Retorna o version_id.
    """
    version_id = version_id_fixo if version_id_fixo else _gerar_id(nome_sessao)

    # Se é nova sessão, a raiz é ela mesma
    if sessao_raiz_id is None:
        sessao_raiz_id = version_id

    versao_num = _proximo_num_versao(sessao_raiz_id) if not version_id_fixo else None
    if version_id_fixo:
        # Mantém o número de versão existente
        index = _load_index()
        entry = next((e for e in index if e["id"] == version_id_fixo), {})
        versao_num = entry.get("versao_num", 1)

    meta = {
        "id": version_id,
        "sessao_raiz_id": sessao_raiz_id,
        "nome_sessao": nome_sessao,
        "nome_versao": nome_versao,
        "versao_num": versao_num,
        "descricao": descricao,
        "autor": autor,
        "criado_em": datetime.now().isoformat(),
        "visao": visao,
        "mes_base": mes_base,
        "pasta_fonte": pasta_fonte,
        "tem_stock": stock_bytes is not None,
        "tem_nb": nb_bytes is not None,
        "n_variaveis_custom": len(nos_custom) if nos_custom else 0,
    }

    zip_path = _session_path(version_id)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        params = {
            "mes_base": mes_base, "visao": visao, "usar_paa": usar_paa,
            "taxa_desconto": taxa_desconto, "percentual_ra": percentual_ra,
            "horizonte_por_produto": horizonte_por_produto or {"default": 12},
            "max_meses_total": max_meses_total,
            "pasta_fonte": pasta_fonte,
            "fallbacks": fallbacks or {},
        }
        zf.writestr("params.json", json.dumps(params, ensure_ascii=False, indent=2))

        for nome_df, df in [("sinistros", df_sinistros),
                             ("comissao", df_comissao),
                             ("gastos", df_gastos)]:
            if df is None:
                continue
            if not isinstance(df, pd.DataFrame):
                try:
                    df = pd.DataFrame(df)
                except Exception:
                    continue
            if len(df) > 0:
                zf.writestr(f"hipoteses/{nome_df}.csv",
                            df.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))

        if df_premissas_proj is not None:
            if not isinstance(df_premissas_proj, pd.DataFrame):
                try:
                    df_premissas_proj = pd.DataFrame(df_premissas_proj)
                except Exception:
                    df_premissas_proj = None
        if df_premissas_proj is not None and len(df_premissas_proj) > 0:
            zf.writestr("premissas_proj.csv",
                        df_premissas_proj.to_csv(sep=";", decimal=",", index=False,
                                                  encoding="utf-8-sig"))

        if stock_bytes:
            zf.writestr("inputs/stock.csv", stock_bytes)
        if nb_bytes:
            zf.writestr("inputs/new_business.csv", nb_bytes)

        if df_fallback_curva is not None and isinstance(df_fallback_curva, pd.DataFrame) and len(df_fallback_curva) > 0:
            zf.writestr("hipoteses/fallback_curva.csv",
                        df_fallback_curva.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))
        if df_fallback_curva_sav is not None and isinstance(df_fallback_curva_sav, pd.DataFrame) and len(df_fallback_curva_sav) > 0:
            zf.writestr("hipoteses/fallback_curva_sav.csv",
                        df_fallback_curva_sav.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))

        if nos_custom:
            zf.writestr("variaveis_custom.json",
                        json.dumps(nos_custom, ensure_ascii=False, indent=2))

    # Atualiza índice
    index = _load_index()
    index = [e for e in index if e["id"] != version_id]
    index.insert(0, meta)
    _save_index(index)

    return version_id


# ─────────────────────────────────────────────────────
# Carregar versão
# ─────────────────────────────────────────────────────

def carregar_versao(version_id: str) -> dict:
    """Carrega uma versão completa a partir do .zip."""
    zip_path = _session_path(version_id)
    if not zip_path.exists():
        raise FileNotFoundError(f"Versão não encontrada: {version_id}")

    resultado = {
        "meta": None, "params": None,
        "df_sinistros": None, "df_comissao": None,
        "df_gastos": None, "df_premissas_proj": None,
        "stock_bytes": None, "nb_bytes": None,
        "nos_custom": [],
        "df_resultado": None, "df_auditoria": None,
        "df_fallback_curva": None, "df_fallback_curva_sav": None,
    }

    with zipfile.ZipFile(zip_path, "r") as zf:
        nomes = zf.namelist()

        if "meta.json" in nomes:
            resultado["meta"] = json.loads(zf.read("meta.json"))
        if "params.json" in nomes:
            resultado["params"] = json.loads(zf.read("params.json"))

        for nome_df in ["sinistros", "comissao", "gastos"]:
            caminho = f"hipoteses/{nome_df}.csv"
            if caminho in nomes:
                from io import StringIO
                resultado[f"df_{nome_df}"] = pd.read_csv(
                    StringIO(zf.read(caminho).decode("utf-8-sig")), sep=";", decimal=","
                )

        from io import StringIO as _StringIO
        for arq_curva, chave_curva in [
            ("hipoteses/fallback_curva.csv",     "df_fallback_curva"),
            ("hipoteses/fallback_curva_sav.csv", "df_fallback_curva_sav"),
        ]:
            if arq_curva in nomes:
                resultado[chave_curva] = pd.read_csv(
                    _StringIO(zf.read(arq_curva).decode("utf-8-sig")), sep=";", decimal=","
                )

        if "premissas_proj.csv" in nomes:
            from io import StringIO
            resultado["df_premissas_proj"] = pd.read_csv(
                StringIO(zf.read("premissas_proj.csv").decode("utf-8-sig")), sep=";", decimal=","
            )

        if "inputs/stock.csv" in nomes:
            resultado["stock_bytes"] = zf.read("inputs/stock.csv")
        if "inputs/new_business.csv" in nomes:
            resultado["nb_bytes"] = zf.read("inputs/new_business.csv")
        if "variaveis_custom.json" in nomes:
            resultado["nos_custom"] = json.loads(zf.read("variaveis_custom.json"))

        for arq, chave in [("resultado.csv", "df_resultado"), ("auditoria.csv", "df_auditoria")]:
            if arq in nomes:
                from io import StringIO
                resultado[chave] = pd.read_csv(
                    StringIO(zf.read(arq).decode("utf-8-sig")), sep=";", decimal=","
                )

    # Merge com arquivo de params auxiliar (auto-save rápido)
    _params_override_path = SESSIONS_DIR / f"{version_id}.params.json"
    if _params_override_path.exists():
        try:
            with open(_params_override_path, "r", encoding="utf-8") as _f:
                _override = json.load(_f)
            if resultado["params"] is None:
                resultado["params"] = _override
            else:
                resultado["params"].update(_override)
        except Exception:
            pass

    return resultado


# ─────────────────────────────────────────────────────
# Salvar resultado calculado na versão existente
# ─────────────────────────────────────────────────────

def listar_versoes_com_resultado() -> list:
    """Retorna todas as versões que têm resultado.csv salvo no zip."""
    index = _load_index()
    resultado = []
    for entry in index:
        zip_path = _session_path(entry["id"])
        if not zip_path.exists():
            continue
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                if "resultado.csv" in zf.namelist():
                    resultado.append(entry)
        except Exception:
            continue
    return resultado


def salvar_resultado_na_versao(version_id: str,
                                df_resultado: pd.DataFrame,
                                df_auditoria: pd.DataFrame = None,
                                fallbacks: dict = None,
                                df_fallback_curva: pd.DataFrame = None,
                                df_fallback_curva_sav: pd.DataFrame = None):
    """
    Adiciona/sobrescreve resultado.csv, auditoria.csv e (opcionalmente) fallbacks
    dentro do zip da versão. Não altera nenhum outro arquivo do zip.
    """
    zip_path = _session_path(version_id)
    if not zip_path.exists():
        return
    _excluir = {"resultado.csv", "auditoria.csv"}
    if fallbacks is not None:
        _excluir.add("params.json")
    if df_fallback_curva is not None:
        _excluir.add("hipoteses/fallback_curva.csv")
    if df_fallback_curva_sav is not None:
        _excluir.add("hipoteses/fallback_curva_sav.csv")

    tmp = str(zip_path) + ".tmp"
    with zipfile.ZipFile(zip_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        _params_escrito = False
        for item in zin.infolist():
            if item.filename not in _excluir:
                zout.writestr(item, zin.read(item.filename))
            elif item.filename == "params.json" and fallbacks is not None:
                # Merge fallbacks into existing params
                existing = json.loads(zin.read("params.json"))
                existing["fallbacks"] = fallbacks
                zout.writestr("params.json", json.dumps(existing, ensure_ascii=False, indent=2))
                _params_escrito = True
        # Se params.json não existia no zip original, cria com fallbacks
        if fallbacks is not None and not _params_escrito:
            zout.writestr("params.json", json.dumps({"fallbacks": fallbacks}, ensure_ascii=False, indent=2))
        if df_resultado is not None and len(df_resultado) > 0:
            zout.writestr("resultado.csv",
                          df_resultado.to_csv(sep=";", decimal=",", index=False,
                                              encoding="utf-8-sig"))
        if df_auditoria is not None and len(df_auditoria) > 0:
            zout.writestr("auditoria.csv",
                          df_auditoria.to_csv(sep=";", decimal=",", index=False,
                                              encoding="utf-8-sig"))
        if df_fallback_curva is not None and isinstance(df_fallback_curva, pd.DataFrame) and len(df_fallback_curva) > 0:
            zout.writestr("hipoteses/fallback_curva.csv",
                          df_fallback_curva.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))
        if df_fallback_curva_sav is not None and isinstance(df_fallback_curva_sav, pd.DataFrame) and len(df_fallback_curva_sav) > 0:
            zout.writestr("hipoteses/fallback_curva_sav.csv",
                          df_fallback_curva_sav.to_csv(sep=";", decimal=",", index=False, encoding="utf-8-sig"))
    os.replace(tmp, zip_path)


# ─────────────────────────────────────────────────────
# Deletar / Exportar / Importar
# ─────────────────────────────────────────────────────

def salvar_params_na_versao(version_id: str, params_update: dict):
    """
    Salva parâmetros atualizados em arquivo auxiliar .params.json (ao lado do zip).
    Operação rápida — não reescreve o zip. O carregar_versao faz merge automático.
    """
    params_path = SESSIONS_DIR / f"{version_id}.params.json"
    # Merge com existente se já houver
    existing = {}
    if params_path.exists():
        try:
            with open(params_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing.update(params_update)
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def deletar_versao(version_id: str) -> bool:
    """Remove uma versão do disco e do índice."""
    zip_path = _session_path(version_id)
    if zip_path.exists():
        zip_path.unlink()
    params_path = SESSIONS_DIR / f"{version_id}.params.json"
    if params_path.exists():
        params_path.unlink()
    index = _load_index()
    index = [e for e in index if e["id"] != version_id]
    _save_index(index)
    return True


def deletar_sessao(sessao_raiz_id: str) -> bool:
    """Remove todas as versões de uma sessão."""
    versoes = listar_versoes(sessao_raiz_id)
    for v in versoes:
        deletar_versao(v["id"])
    return True


def exportar_versao_zip(version_id: str) -> bytes:
    zip_path = _session_path(version_id)
    if not zip_path.exists():
        raise FileNotFoundError(f"Versão não encontrada: {version_id}")
    return zip_path.read_bytes()


def importar_sessao_zip(zip_bytes: bytes, novo_nome: str = None) -> str:
    """Importa uma versão a partir de bytes de um zip externo como nova sessão."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(zip_bytes)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            meta = json.loads(zf.read("meta.json"))
            params = json.loads(zf.read("params.json")) if "params.json" in zf.namelist() else {}

        nome_sessao = novo_nome or meta.get("nome_sessao", meta.get("nome", "importado"))
        novo_id = _gerar_id(nome_sessao)
        destino = _session_path(novo_id)
        shutil.copy2(tmp_path, destino)

        meta["id"] = novo_id
        meta["sessao_raiz_id"] = novo_id
        meta["nome_sessao"] = nome_sessao
        meta["nome_versao"] = "V1"
        meta["versao_num"] = 1
        meta["importado_em"] = datetime.now().isoformat()

        _atualizar_meta_no_zip(destino, meta)

        index = _load_index()
        index.insert(0, meta)
        _save_index(index)

        return novo_id
    finally:
        os.unlink(tmp_path)


# ─────────────────────────────────────────────────────
# Atualizar pasta fonte
# ─────────────────────────────────────────────────────

def atualizar_pasta_sessao(version_id: str, pasta_fonte: str):
    """Atualiza pasta_fonte em meta.json e params.json do zip."""
    zip_path = _session_path(version_id)
    if not zip_path.exists():
        return
    tmp = str(zip_path) + ".tmp"
    with zipfile.ZipFile(zip_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "meta.json":
                m = json.loads(data)
                m["pasta_fonte"] = pasta_fonte
                zout.writestr("meta.json", json.dumps(m, ensure_ascii=False, indent=2))
            elif item.filename == "params.json":
                p = json.loads(data)
                p["pasta_fonte"] = pasta_fonte
                zout.writestr("params.json", json.dumps(p, ensure_ascii=False, indent=2))
            else:
                zout.writestr(item, data)
    os.replace(tmp, zip_path)

    index = _load_index()
    for e in index:
        if e["id"] == version_id:
            e["pasta_fonte"] = pasta_fonte
            break
    _save_index(index)


# ─────────────────────────────────────────────────────
# Compatibilidade com código legado
# ─────────────────────────────────────────────────────

def salvar_sessao(nome, descricao, autor, mes_base, visao, usar_paa,
                  taxa_desconto, percentual_ra, horizonte_por_produto,
                  pasta_fonte="", df_sinistros=None, df_comissao=None,
                  df_gastos=None, df_premissas_proj=None, stock_bytes=None,
                  nb_bytes=None, nos_custom=None, parent_id=None,
                  session_id_fixo=None) -> str:
    """Wrapper legado — redireciona para salvar_versao."""
    return salvar_versao(
        nome_sessao=nome, nome_versao="V1", descricao=descricao, autor=autor,
        sessao_raiz_id=None, mes_base=mes_base, visao=visao, usar_paa=usar_paa,
        taxa_desconto=taxa_desconto, percentual_ra=percentual_ra,
        horizonte_por_produto=horizonte_por_produto, pasta_fonte=pasta_fonte,
        df_sinistros=df_sinistros, df_comissao=df_comissao, df_gastos=df_gastos,
        df_premissas_proj=df_premissas_proj, stock_bytes=stock_bytes,
        nb_bytes=nb_bytes, nos_custom=nos_custom,
        version_id_fixo=session_id_fixo,
    )


def carregar_sessao(session_id: str) -> dict:
    """Wrapper legado."""
    return carregar_versao(session_id)


def clonar_sessao(session_id: str, novo_nome: str, novo_autor: str = "") -> str:
    """Clona uma versão como nova sessão independente."""
    dados = carregar_versao(session_id)
    params = dados["params"] or {}
    meta = dados["meta"] or {}
    return salvar_versao(
        nome_sessao=novo_nome, nome_versao="V1",
        descricao=f"Clonado de: {meta.get('nome_sessao', meta.get('nome', session_id))}",
        autor=novo_autor or meta.get("autor", ""),
        sessao_raiz_id=None,
        mes_base=params.get("mes_base", ""), visao=params.get("visao", "LOCAL"),
        usar_paa=params.get("usar_paa", True), taxa_desconto=params.get("taxa_desconto", 0.0),
        percentual_ra=params.get("percentual_ra", 0.05),
        horizonte_por_produto=params.get("horizonte_por_produto", {"default": 12}),
        max_meses_total=params.get("max_meses_total", 120),
        pasta_fonte=params.get("pasta_fonte", ""),
        df_sinistros=dados["df_sinistros"], df_comissao=dados["df_comissao"],
        df_gastos=dados["df_gastos"], df_premissas_proj=dados.get("df_premissas_proj"),
        stock_bytes=dados["stock_bytes"], nb_bytes=dados["nb_bytes"],
        nos_custom=dados["nos_custom"],
    )


def listar_sessoes_df() -> pd.DataFrame:
    """Wrapper legado."""
    return listar_sessoes_raiz_df()


def deletar_sessao_by_id(session_id: str) -> bool:
    """Deleta apenas uma versão específica."""
    return deletar_versao(session_id)


def exportar_sessao_zip(session_id: str) -> bytes:
    return exportar_versao_zip(session_id)


def _atualizar_meta_no_zip(zip_path: Path, novo_meta: dict):
    tmp = str(zip_path) + ".tmp"
    with zipfile.ZipFile(zip_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "meta.json":
                zout.writestr("meta.json", json.dumps(novo_meta, ensure_ascii=False, indent=2))
            else:
                zout.writestr(item, zin.read(item.filename))
    os.replace(tmp, zip_path)
