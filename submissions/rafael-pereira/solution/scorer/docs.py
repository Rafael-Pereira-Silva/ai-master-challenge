"""Documentação com números gerados.

1. Blocos `<!-- AUTO:nome -->...<!-- /AUTO:nome -->` dos .md são reescritos a partir de `facts.json`
   (e, a partir do bloco 3, de `backtest_metrics.json`): `python -m scorer.docs`.
   `python -m scorer.docs --check` só confere (exit 1 se algum documento estiver desatualizado).
2. Conferência dos números da prosa (fora dos blocos AUTO): `unmatched_numbers` devolve os números do
   texto que não saem de nenhum fato; `tests/test_docs_numbers.py` exige que a lista seja vazia.

Para criar um bloco novo, registre um renderizador com `@block("nome")`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from . import config
from .facts import load_facts
from .fmt import fmt_date, fmt_dec, fmt_int, fmt_month, fmt_pct, fmt_pp, fmt_quarter, round_half_up

# =============================================================================================
# Blocos AUTO
# =============================================================================================
AUTO_RE = re.compile(r"<!-- AUTO:(?P<name>[\w-]+) -->\n(?P<body>.*?)\n?<!-- /AUTO:(?P=name) -->", re.S)
AUTO_OPEN_RE = re.compile(r"<!-- AUTO:([\w-]+) -->")

BLOCKS: dict[str, Callable[[dict], str]] = {}


def block(name: str):
    """Registra o renderizador de um bloco AUTO. Ele recebe `sources` ({'facts': ..., 'backtest': ...})."""

    def register(func):
        BLOCKS[name] = func
        return func

    return register


def load_sources() -> dict:
    """Carrega as fontes de números: facts.json e, se já existir, backtest_metrics.json."""
    backtest = None
    if config.BACKTEST_JSON.exists():
        with open(config.BACKTEST_JSON, encoding="utf-8") as handle:
            backtest = json.load(handle)
    return {"facts": load_facts(), "backtest": backtest}


def render_blocks(sources: dict | None = None) -> dict[str, str]:
    """Renderiza todos os blocos registrados: nome -> markdown."""
    sources = sources or load_sources()
    return {name: func(sources).strip("\n") for name, func in BLOCKS.items()}


def render_text(text: str, blocks: dict[str, str]) -> str:
    """Troca o conteúdo de cada bloco AUTO do texto; erro se o marcador não tem renderizador."""
    opened = AUTO_OPEN_RE.findall(text)
    if len(opened) != len(AUTO_RE.findall(text)):
        raise ValueError("marcador AUTO sem fechamento (ou com nome diferente no fechamento)")
    unknown = sorted(set(opened) - set(blocks))
    if unknown:
        raise KeyError(f"marcador AUTO sem renderizador: {unknown}")

    def replace(match: re.Match) -> str:
        name = match.group("name")
        return f"<!-- AUTO:{name} -->\n{blocks[name]}\n<!-- /AUTO:{name} -->"

    return AUTO_RE.sub(replace, text)


def read_doc(path) -> str:
    return Path(path).read_text(encoding="utf-8")  # a leitura em modo texto já normaliza CRLF para LF


def inject(path, blocks: dict[str, str] | None = None, write: bool = True) -> bool:
    """Atualiza os blocos AUTO de um documento. Devolve True se o texto mudou."""
    blocks = blocks if blocks is not None else render_blocks()
    old = read_doc(path)
    new = render_text(old, blocks)
    if new != old and write:
        Path(path).write_text(new, encoding="utf-8", newline="\n")
    return new != old


# ---------------------------------------------------------------------------------------------
# Formatação das tabelas
# ---------------------------------------------------------------------------------------------
def md_table(headers: list[str], rows: list[list], align: str | None = None) -> str:
    """Tabela markdown. `align` tem uma letra por coluna ('l' ou 'r'); o padrão é texto + números."""
    align = align or "l" + "r" * (len(headers) - 1)
    rule = ["---:" if a == "r" else ":---" for a in align]
    lines = [f"| {' | '.join(headers)} |", f"| {' | '.join(rule)} |"]
    lines += [f"| {' | '.join(str(cell) for cell in row)} |" for row in rows]
    return "\n".join(lines)


def _yes(flag: bool) -> str:
    return "sim" if flag else "não"


def _num(x) -> str:
    """Inteiro sem casas; com meio dia, uma casa."""
    return fmt_int(x) if float(x).is_integer() else fmt_dec(x, 1)


# ---------------------------------------------------------------------------------------------
# Renderizadores do DATA_QUALITY.md (investigações 2a, 2b e 2c)
# ---------------------------------------------------------------------------------------------
@block("dq-meses")
def _dq_meses(src: dict) -> str:
    rows = [
        [fmt_month(r["mes"]), fmt_int(r["n"]), fmt_pct(r["win_rate"]), _num(r["ciclo_mediano"]), fmt_pct(r["pct_ciclo_rapido"], 0)]
        for r in src["facts"]["evidencia_2a_q1"]["por_mes_de_fechamento"]
    ]
    fast = src["facts"]["ciclos"]["ciclo_rapido_dias"]
    headers = ["Mês de fechamento", "Fechados", "Win rate", "Ciclo mediano (dias)", f"% com ciclo de até {fast} dias"]
    return md_table(headers, rows)


@block("dq-trimestres")
def _dq_trimestres(src: dict) -> str:
    ev = src["facts"]["evidencia_2a_q1"]
    rows = [
        [fmt_quarter(r["trimestre"]), fmt_int(r["n"]), fmt_pct(r["win_rate"]), _num(r["ciclo_mediano"])]
        for r in ev["por_trimestre_de_fechamento"]
    ]
    after = [r for r in ev["por_trimestre_de_fechamento"] if r["trimestre"] != ev["primeiro_trimestre"]]
    rows.append(
        [f"Depois de {fmt_quarter(ev['primeiro_trimestre'])}", fmt_int(sum(r["n"] for r in after)),
         fmt_pct(ev["win_rate_depois_do_primeiro_trimestre"]), "—"]
    )
    return md_table(["Trimestre de fechamento", "Fechados", "Win rate", "Ciclo mediano (dias)"], rows)


@block("dq-coortes")
def _dq_coortes(src: dict) -> str:
    fast = src["facts"]["ciclos"]["ciclo_rapido_dias"]
    rows = []
    for r in src["facts"]["evidencia_2a_q1"]["por_coorte_de_engajamento"]:
        floor, gap = r["piso_do_recorte_dias"], r["folga_dias"]
        rows.append(
            [fmt_month(r["mes"]), fmt_int(r["n_fechados"]), fmt_pct(r["win_rate"]), fmt_int(r["ciclo_min"]),
             "—" if floor is None else fmt_int(floor), "—" if gap is None else fmt_int(gap),
             fmt_pct(r["pct_ciclo_rapido"], 0)]
        )
    headers = ["Coorte (mês de engajamento)", "Fechados", "Win rate", "Ciclo mínimo (dias)",
               "Piso do recorte (dias)", "Folga (dias)", f"% com ciclo de até {fast} dias"]
    return md_table(headers, rows)


@block("dq-cruzamento")
def _dq_cruzamento(src: dict) -> str:
    ev = src["facts"]["evidencia_2a_q1"]
    table = ev["cruzamento_trimestre_engajamento_x_fechamento"]
    columns = sorted({col for row in table.values() for col in row})
    rows = [[fmt_quarter(eng)] + [fmt_int(table[eng][c]) if c in table[eng] else "—" for c in columns] for eng in table]
    text = md_table(["Engajado em \\ fechado em"] + [fmt_quarter(c) for c in columns], rows)
    return (
        f"{text}\n\nFechados no mesmo trimestre do engajamento: {fmt_int(ev['fechados_no_mesmo_trimestre'])}; "
        f"no trimestre seguinte: {fmt_int(ev['fechados_no_trimestre_seguinte'])}; "
        f"fora da regra: {fmt_int(ev['fechados_fora_da_regra_q_q1'])}."
    )


@block("dq-posicao-trimestre")
def _dq_posicao(src: dict) -> str:
    fast = src["facts"]["ciclos"]["ciclo_rapido_dias"]
    names = {1: "1º mês (jan, abr, jul, out)", 2: "2º mês (fev, mai, ago, nov)", 3: "3º mês (mar, jun, set, dez)"}
    rows = [
        [names[r["mes_do_trimestre"]], fmt_int(r["n"]), fmt_pct(r["win_rate"]), _num(r["ciclo_mediano"]),
         fmt_pct(r["pct_ciclo_rapido"], 0)]
        for r in src["facts"]["evidencia_2a_q1"]["por_mes_dentro_do_trimestre"]
    ]
    headers = ["Mês dentro do trimestre", "Fechados", "Win rate", "Ciclo mediano (dias)", f"% com ciclo de até {fast} dias"]
    return md_table(headers, rows)


@block("dq-criterio-2a")
def _dq_criterio_2a(src: dict) -> str:
    ev = src["facts"]["evidencia_2a_q1"]
    crit = ev["criterio"]
    first_month = fmt_month(ev["primeiro_mes_com_fechamento"])
    months = ", ".join(fmt_month(m)[:3] for m in crit["c2_meses_de_fim_de_trimestre"])
    rows = [
        [f"(i) o {fmt_quarter(ev['primeiro_trimestre'])} só tem fechamentos em {first_month}",
         f"{fmt_int(crit['c1_fechamentos_do_1o_trimestre_fora_do_1o_mes'])} fechamentos fora de {first_month}",
         "0", _yes(crit["c1_vale"])],
        [f"(ii) win rate de {first_month} perto dos meses de fim de trimestre ({months})",
         f"{fmt_pct(crit['c2_win_rate_do_1o_mes'])} contra {fmt_pct(crit['c2_media_dos_meses_de_fim_de_trimestre'])} "
         f"({fmt_pp(crit['c2_diferenca_pp'] / 100)})",
         f"±{fmt_int(crit['c2_tolerancia_pp'])} pp", _yes(crit["c2_vale"])],
        [f"(iii) coortes engajadas antes de {fmt_date(ev['primeiro_fechamento'])} sem ciclos curtos (truncamento)",
         f"maior folga entre o ciclo mínimo e o piso do recorte: {fmt_int(crit['c3_maior_folga_dias'])} dias "
         f"({fmt_int(crit['c3_coortes_avaliadas'])} coortes)",
         f"{fmt_int(crit['c3_tolerancia_dias'])} dias", _yes(crit["c3_vale"])],
    ]
    table = md_table(["Condição", "Medido", "Limite", "Vale?"], rows, "lllr")
    verdict = (
        "**Resultado: artefato de recorte confirmado (as três condições valem).**"
        if crit["artefato_de_recorte"]
        else "**Resultado: artefato de recorte NÃO confirmado (alguma condição falhou).**"
    )
    support = (
        f"Reforço sem tolerância: nas coortes com piso de {fmt_int(src['facts']['ciclos']['ciclo_rapido_dias'])} "
        f"dias ou mais, {fmt_pct(crit['c3_pct_ciclo_rapido_coortes_com_piso_alto'], 0)} dos fechamentos são rápidos; "
        f"nas coortes sem recorte, no mínimo {fmt_pct(crit['c3_pct_ciclo_rapido_coortes_sem_recorte_minimo'], 0)}."
    )
    return f"{table}\n\n{verdict}\n\n{support}"


@block("dq-razao-preco")
def _dq_razao(src: dict) -> str:
    ev = src["facts"]["evidencia_2c_close_value"]

    def row(label: str, s: dict) -> list:
        return [label, fmt_int(s["n"])] + [fmt_dec(s[k], 3) for k in ("media", "mediana", "p5", "p95", "min", "max")]

    rows = [row("Todos os ganhos", ev["geral"])]
    rows += [row(f"Produto: {name}", s) for name, s in ev["por_produto"].items()]
    rows += [row(f"Fechamento em {fmt_quarter(q)}", s) for q, s in ev["por_trimestre_de_fechamento"].items()]
    table = md_table(["Recorte", "Ganhos", "Média", "Mediana", "p5", "p95", "Mín", "Máx"], rows)
    crit = ev["criterio"]
    lines = [
        f"- Média por produto: de {fmt_dec(crit['media_por_produto_minima'], 3)} a "
        f"{fmt_dec(crit['media_por_produto_maxima'], 3)} (faixa aceita: {fmt_dec(crit['faixa_aceita_min'], 2)} a "
        f"{fmt_dec(crit['faixa_aceita_max'], 2)}): {_yes(crit['faixa_vale'])}.",
        f"- Variação da média entre trimestres: {fmt_dec(crit['variacao_entre_trimestres_pp'], 1)} pp "
        f"(limite: {fmt_int(crit['variacao_aceita_pp'])} pp): {_yes(crit['variacao_vale'])}.",
        f"- Perdidos com `close_value` = 0: {fmt_int(ev['perdidos_com_close_value_zero'])} de {fmt_int(ev['perdidos_n'])}; "
        f"ganhos com `close_value` = 0: {fmt_int(ev['ganhos_com_close_value_zero'])}.",
    ]
    return table + "\n\n" + "\n".join(lines)


@block("dq-vendedores")
def _dq_vendedores(src: dict) -> str:
    ev = src["facts"]["evidencia_2b_vendedores"]

    def people(items: list[dict]) -> list[list]:
        return [[r["sales_agent"], r["manager"], r["regional_office"]] for r in items]

    headers = ["Vendedor", "Manager", "Região"]
    summary = (
        f"Cadastro: {fmt_int(ev['vendedores_cadastro'])} vendedores; com algum deal: {fmt_int(ev['vendedores_com_deals'])}; "
        f"com deal aberto na data de referência: {fmt_int(ev['vendedores_com_deals_abertos'])}; "
        f"sem nenhum deal: {fmt_int(ev['vendedores_sem_deals'])}; só com deals fechados: {fmt_int(ev['vendedores_so_com_fechados'])}."
    )
    return "\n\n".join(
        [
            summary,
            "**Sem nenhum deal no CRM**\n\n" + md_table(headers, people(ev["sem_deals"]), "lll"),
            "**Só com deals fechados (nenhum aberto)**\n\n" + md_table(headers, people(ev["so_com_fechados"]), "lll"),
            "Times sem nenhum vendedor fora do pipeline: " + ", ".join(ev["managers_sem_vendedor_sem_deals"]) + ".",
        ]
    )


# =============================================================================================
# Conferência dos números da prosa
# =============================================================================================
_NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?"  # número PT-BR: 1.291 | 3,2 | 1.234,5 | 138
_TOKEN_RE = re.compile(
    rf"(?P<usd>US\$\s?(?P<usd_num>{_NUM})(?:\s?(?P<unit>mil|mi)\b)?)"
    rf"|(?P<pct>(?<![\w.,])(?P<pct_num>{_NUM})\s?%)"
    rf"|(?P<dec>(?<![\w.,])(?:\d{{1,3}}(?:\.\d{{3}})+,\d+|\d+,\d+)(?!\w))"
    rf"|(?P<int>(?<![\w.,])(?:\d{{1,3}}(?:\.\d{{3}})+|\d{{3,}})(?!\w))"
)
_UNIT_SCALE = {None: 1.0, "mil": 1e3, "mi": 1e6}
_MONTH_ABBR = "jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez"
_STRIP_PATTERNS = [  # (padrão, flags): trechos que não são "números do texto"
    (r"```.*?```", re.S),  # blocos de código
    (r"<!--.*?-->", re.S),  # comentários HTML
    (r"`[^`\n]*`", 0),  # código inline
    (r"\]\([^)\n]*\)", 0),  # destino de link
    (r"https?://\S+", 0),  # URL solta
    (r"\b\d{1,2}/\d{1,2}/\d{4}\b", 0),  # dd/mm/aaaa
    (r"\b\d{4}-\d{2}-\d{2}\b", 0),  # aaaa-mm-dd
    (rf"\b(?:{_MONTH_ABBR})/\d{{4}}\b", re.I),  # mmm/aaaa
    (r"\b\d{1,2}/\d{4}\b", 0),  # mm/aaaa
    (r"(?<![\d.,])20(?:1[6-9]|2[0-6])(?!\d)", 0),  # anos 2016 a 2026
]
_LINE_PREFIX_RE = re.compile(r"^(?P<lead>\s*(?:#{1,6}\s+)?)(?P<num>\d+(?:\.\d+)*[.)])(?=\s)", re.M)


@dataclass(frozen=True)
class NumberToken:
    text: str  # como está no documento
    kind: str  # 'usd' | 'pct' | 'dec' | 'int'
    value: float  # valor exibido
    decimals: int  # casas decimais exibidas
    scale: float  # 1, 1e3 ('mil') ou 1e6 ('mi'), só para US$
    line: int


def _blank(match: re.Match) -> str:
    """Troca o trecho por espaços, mantendo as quebras de linha (os números de linha não mudam)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def names_with_digits() -> list[str]:
    """Nomes de produto e conta que contêm dígitos (ex.: 'GTK 500'), que não são números do texto."""
    names = []
    for file, column in [("products.csv", "product"), ("accounts.csv", "account")]:
        names += pd.read_csv(config.RAW_DIR / file, encoding="utf-8")[column].dropna().tolist()
    return sorted({n for n in names if any(ch.isdigit() for ch in n)}, key=len, reverse=True)


def prose_text(text: str, ignore_terms=()) -> str:
    """Texto sem o que não conta como número da prosa: blocos AUTO, código, links, datas, anos,
    numeração de títulos e listas e nomes com dígitos. Mantém o número de linhas."""
    text = AUTO_RE.sub(_blank, text)
    for pattern, flags in _STRIP_PATTERNS:
        text = re.sub(pattern, _blank, text, flags=flags)
    for term in ignore_terms:
        text = re.sub(re.escape(term), _blank, text, flags=re.I)
    return _LINE_PREFIX_RE.sub(lambda m: m.group("lead") + " " * len(m.group("num")), text)


def _parse_pt(number: str) -> tuple[float, int]:
    decimals = len(number.split(",")[1]) if "," in number else 0
    return float(number.replace(".", "").replace(",", ".")), decimals


def extract_number_tokens(text: str) -> list[NumberToken]:
    """Números a conferir: US$, porcentagens, decimais com vírgula e inteiros >= 100 ou com ponto de milhar."""
    tokens = []
    for match in _TOKEN_RE.finditer(text):
        kind = match.lastgroup  # grupo mais externo que casou: usd, pct, dec ou int
        number = match.group(f"{kind}_num") if kind in ("usd", "pct") else match.group(kind)
        value, decimals = _parse_pt(number)
        scale = _UNIT_SCALE[match.group("unit")] if kind == "usd" else 1.0
        line = text.count("\n", 0, match.start()) + 1
        tokens.append(NumberToken(match.group(0), kind, value, decimals, scale, line))
    return tokens


def _numeric_leaves(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _numeric_leaves(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _numeric_leaves(value)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield abs(float(obj))


def number_pool(sources: dict) -> list[float]:
    """Todos os valores numéricos dos JSONs de fatos mais as constantes estruturais permitidas."""
    values = {abs(float(c)) for c in config.ALLOWED_CONSTANTS}
    for source in sources.values():
        if source is not None:
            values.update(_numeric_leaves(source))
    return sorted(values)


def _close(a: float, b: float) -> bool:
    return abs(a - b) < 1e-9


def token_matches(token: NumberToken, pool: list[float]) -> bool:
    """O valor exibido, com a precisão exibida, bate com algum valor do pool?

    US$: o valor é dividido pela unidade exibida (mi, mil). Porcentagem: vale a fração (x100) ou o valor
    já em pontos percentuais. Decimal e inteiro: comparação direta. O sinal é ignorado.
    """
    d = token.decimals
    for v in pool:
        if token.kind == "usd":
            hit = _close(round_half_up(v / token.scale, d), token.value)
        elif token.kind == "pct":
            hit = _close(round_half_up(v * 100, d), token.value) or _close(round_half_up(v, d), token.value)
        else:  # 'dec' e 'int'
            hit = _close(round_half_up(v, d), token.value)
        if hit:
            return True
    return False


def unmatched_numbers(text: str, pool: list[float], ignore_terms=()) -> list[NumberToken]:
    """Números da prosa que não saem de nenhum fato."""
    tokens = extract_number_tokens(prose_text(text, ignore_terms))
    return [t for t in tokens if not token_matches(t, pool)]


# =============================================================================================
# CLI
# =============================================================================================
def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Reescreve os blocos AUTO dos documentos a partir dos JSONs de fatos.")
    parser.add_argument("--check", action="store_true", help="não escreve; exit 1 se algum documento estiver desatualizado")
    args = parser.parse_args(argv)

    blocks = render_blocks()
    stale = []
    for path in config.COVERED_DOCS:
        changed = inject(path, blocks, write=not args.check)
        if changed:
            stale.append(path)
        status = "desatualizado" if (changed and args.check) else ("atualizado" if changed else "sem mudanças")
        print(f"{Path(path).name}: {status}")
    if args.check and stale:
        print("Rode `python -m scorer.docs` para atualizar.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
