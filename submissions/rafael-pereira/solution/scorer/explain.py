"""Explicação em linguagem de vendedor: frases curtas por deal e as 5 linhas de "Como funciona o score".

Todo número vem do modelo do corte (`ScoreModel`) e da linha do deal, formatado por `fmt.py`.
Sem jargão: "chance" (não probabilidade), nada de logit ou coeficiente.
"""

from __future__ import annotations

from . import config, fmt
from .score import ScoreModel

NO_ACCOUNT_SENTENCE = "Conta não informada no CRM — preencha; isso não muda o score."
NO_ACCOUNT_SENTENCE_QUALIFIQUE = "Conta não informada no CRM — preencha; isso não muda a ordem da lista."


def _days(n) -> str:
    """'1 dia', '12 dias'."""
    n = int(n)
    return f"{fmt.fmt_int(n)} {'dia' if n == 1 else 'dias'}"


def _pct(p: float) -> str:
    """Porcentagem inteira da chance; 'menos de 1%' quando arredonda para zero."""
    value = int(fmt.round_half_up(100 * p))
    return "menos de 1%" if value == 0 else f"{value}%"


def _value_sentence(row) -> str:
    return (
        f"{row['product']}: valor de tabela {fmt.fmt_usd(row['sales_price'])}; "
        f"valor esperado {fmt.fmt_usd(row['expected_value'])}."
    )


def _foque(row, model: ScoreModel) -> list[str]:
    left = int(row["days_to_knot"])
    window = (
        f"Ainda na janela boa: a chance só começa a cair depois de {_days(model.knot_days)} "
        f"({'falta' if left == 1 else 'faltam'} {_days(left)})."
        if left > 0
        else f"Hoje é o último dia da janela boa: depois de {_days(model.knot_days)} a chance começa a cair."
    )
    return [
        f"Aberto há {_days(row['age_days'])}. No histórico, deals em Engaging com essa idade foram ganhos "
        f"em {_pct(row['p_win'])} dos casos nos {model.horizon_days} dias seguintes.",
        _value_sentence(row),
        window,
    ]


def _reative(row, model: ScoreModel) -> list[str]:
    left = int(row["days_to_limpe"])
    deadline = (
        f"Nenhum deal foi ganho depois de {_days(model.limpe_after_days)} aberto "
        f"— {'falta' if left == 1 else 'faltam'} {_days(left)}. Fale com o cliente esta semana."
        if left > 0
        else f"Hoje é o último dia: nenhum deal foi ganho depois de {_days(model.limpe_after_days)} aberto. "
        "Fale com o cliente hoje."
    )
    return [
        f"Aberto há {_days(row['age_days'])}: a chance de ganho em {model.horizon_days} dias caiu de "
        f"{_pct(model.p_fresh)} (deal novo) para {_pct(row['p_win'])}.",
        _value_sentence(row),
        deadline,
    ]


def _limpe(row, model: ScoreModel) -> list[str]:
    return [
        f"Aberto há {_days(row['age_days'])} — mais do que qualquer deal já ganho no histórico "
        f"({_days(model.limpe_after_days)}).",
        "Provável deal parado ou CRM desatualizado: confirme com o cliente e encerre ou atualize.",
        f"São {fmt.fmt_usd(row['sales_price'])} inflando o pipeline.",
    ]


def _qualifique(row, model: ScoreModel) -> list[str]:
    return [
        "Ainda em Prospecting, sem data de engajamento: o histórico não permite estimar a chance.",
        f"{row['product']}: valor de tabela {fmt.fmt_usd(row['sales_price'])}. "
        "Qualifique (marque a primeira conversa) ou descarte.",
    ]


_BUILDERS = {"Foque": _foque, "Reative": _reative, "Limpe": _limpe, "Qualifique": _qualifique}


def explain_deal(row, model: ScoreModel) -> list[str]:
    """De 2 a 4 frases curtas sobre o deal, na ordem em que devem ser lidas.

    `row` é uma linha de `score.score_deals` (Series ou dict). A conta ausente nunca muda o score,
    mas gera um aviso de higiene de CRM.
    """
    category = row["category"]
    sentences = _BUILDERS[category](row, model)
    if not bool(row["has_account"]):
        sentences.append(NO_ACCOUNT_SENTENCE_QUALIFIQUE if category == "Qualifique" else NO_ACCOUNT_SENTENCE)
    return sentences


def _plateau_line(model: ScoreModel) -> str:
    curve = model.curve
    start = f"Um deal novo tem {_pct(model.p_fresh)} de chance de ser ganho nos próximos {model.horizon_days} dias"
    half = curve.halving_days
    if half is None:
        return f"{start}, e a chance não muda com a idade."
    if model.knot_days == 0:
        return f"{start}; a chance cai desde o primeiro dia e chega à metade em {_days(round(half))}."
    return (
        f"{start}, e essa chance se mantém até {_days(model.knot_days)} de idade. "
        f"Depois disso ela cai e, {_days(round(half))} depois, vale metade."
    )


def _result_line(headline_metrics: dict | None) -> str:
    suffix = "Vendedor não entra no score."
    if not headline_metrics:
        return f"O teste no passado ainda não foi rodado. {suffix}"
    return (
        f"Testado no passado em {fmt.fmt_int(headline_metrics['n_cortes'])} datas: o top {fmt.fmt_pct(config.TOP_FRAC, 0)} do score capturou "
        f"{fmt.fmt_pct(headline_metrics['receita_score'], 0)} da receita ganha depois, contra "
        f"{fmt.fmt_pct(headline_metrics['receita_valor'], 0)} ordenando por valor e "
        f"{fmt.fmt_pct(headline_metrics['receita_recencia'], 0)} pelos mais recentes. {suffix}"
    )


def how_it_works(model: ScoreModel, headline_metrics: dict | None = None) -> list[str]:
    """As 5 linhas de "Como funciona o score".

    `headline_metrics` (preenchido pelo backtest): `n_cortes`, `receita_score`, `receita_valor` e
    `receita_recencia`, todos em fração (média dos cortes). Sem ele, a linha 5 avisa que o teste não rodou.
    """
    curve = model.curve
    first, last = curve.train_snapshots[0], curve.train_snapshots[-1]
    ratio = model.price_max / model.price_min
    reative = (
        f"Reative: de {_days(model.knot_days + 1)} a {_days(model.limpe_after_days)}."
        if model.limpe_after_days > model.knot_days
        else "Reative: nenhum."
    )
    return [
        f"A chance vem do histórico: {fmt.fmt_int(len(curve.train_snapshots))} fotos mensais do pipeline, "
        f"de {fmt.fmt_date(first)} a {fmt.fmt_date(last)}, com {fmt.fmt_int(curve.train_rows)} casos de deal "
        f"aberto e o que aconteceu com cada um nos {model.horizon_days} dias seguintes.",
        _plateau_line(model),
        "Valor esperado = chance × preço de tabela. O score (0 a 100) coloca esse valor numa escala de log: "
        f"100 é um deal novo do produto mais caro, que custa {fmt.fmt_int(ratio)} vezes o mais barato.",
        f"Foque: até {_days(model.knot_days)} de idade. {reative} "
        f"Limpe: acima de {_days(model.limpe_after_days)}, mais do que qualquer deal já ganho. "
        "Qualifique: Prospecting, que não tem data nem score.",
        _result_line(headline_metrics),
    ]
