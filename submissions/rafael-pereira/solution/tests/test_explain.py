"""Testes de `explain.py`: frases curtas e sem jargão, números do modelo do corte, conta ausente."""

import re

import pytest

from scorer import clean, config, explain, score

BANNED = ["nan", "none", "<na>", "nat", "logit", "probabilidade", "coeficiente", "sigmoid", "erro padrão"]


@pytest.fixture(scope="module")
def deals():
    return clean.load_deals()


@pytest.fixture(scope="module")
def today(deals):
    T = config.DEFAULT_REFERENCE_DATE
    model = score.fit_model(deals, T)
    return model, score.score_deals(deals, T, model, include_prospecting=True)


def model_with(knot=95, limpe=138, slope=-2.59, p_fresh_logit=-0.41) -> score.ScoreModel:
    curve = score.AgeCurve(knot, p_fresh_logit, slope, 0.33, 13100, ("2017-03-31", "2017-09-30"))
    return score.ScoreModel(curve, limpe, price_min=55.0, price_max=26768.0, as_of_date="2017-12-31")


def row(category, **overrides) -> dict:
    base = {
        "category": category, "age_days": 60, "p_win": 0.40, "expected_value": 1928.4, "sales_price": 4821,
        "product": "GTX Pro", "has_account": True, "days_to_knot": 35, "days_to_limpe": 78,
        "sales_agent": "Fulana de Tal",
    }
    return {**base, **overrides}


def test_every_deal_today_gets_two_to_four_short_clean_sentences(today):
    model, scored = today
    assert set(scored["category"]) == set(config.CATEGORIES)
    for _, deal in scored.iterrows():
        sentences = explain.explain_deal(deal, model)
        assert 2 <= len(sentences) <= 4, (deal["opportunity_id"], sentences)
        text = " ".join(sentences).lower()
        assert not any(re.search(rf"\b{re.escape(word)}\b", text) for word in BANNED), sentences
        assert all(len(s) <= 160 and s.endswith(".") for s in sentences), sentences
        assert deal["sales_agent"].lower() not in text  # o vendedor nunca aparece como fator


def test_quoted_percentages_equal_the_rounded_chance(today):
    model, scored = today
    for category in ("Foque", "Reative"):
        deal = scored[scored["category"] == category].iloc[3]
        sentences = explain.explain_deal(deal, model)
        shown = [int(n) for n in re.findall(r"(\d+)%", " ".join(sentences[:2]))]
        expected = [round(100 * model.p_fresh), round(100 * deal["p_win"])] if category == "Reative" else [
            round(100 * deal["p_win"])]
        assert shown == expected, (category, sentences[0])


def test_sentences_have_the_expected_content_per_list():
    model = model_with()
    foque = explain.explain_deal(row("Foque"), model)
    assert foque[0] == "GTX Pro: US$ 4.821 de tabela, valor esperado US$ 1.928; janela boa por mais 35 dias."
    assert "Aberto há 60 dias" in foque[1] and "40%" in foque[1] and "90 dias seguintes" in foque[1]
    assert "depois de 95 dias" in foque[2]

    reative = explain.explain_deal(row("Reative", age_days=110, p_win=0.2, expected_value=964.2, days_to_knot=None,
                                       days_to_limpe=28), model)
    assert "caiu de 40% (deal novo) para 20%" in reative[0]
    assert "depois de 138 dias" in reative[2] and "faltam 28 dias" in reative[2]

    limpe = explain.explain_deal(row("Limpe", age_days=300, p_win=1e-9, days_to_knot=None, days_to_limpe=None), model)
    assert "300 dias" in limpe[0] and "138 dias" in limpe[0]
    assert limpe[2] == "São US$ 4.821 inflando o pipeline."
    assert "Pergunte ao cliente" in limpe[1] and "marque Lost" in limpe[1] and "Reative ou Foque" in limpe[1]

    qualifique = explain.explain_deal(row("Qualifique", age_days=None, p_win=None, expected_value=None), model)
    assert len(qualifique) == 2 and "Prospecting" in qualifique[0] and "US$ 4.821" in qualifique[1]


def test_missing_account_adds_exactly_one_hygiene_sentence():
    model = model_with()
    for category in config.CATEGORIES:
        with_account = explain.explain_deal(row(category), model)
        without = explain.explain_deal(row(category, has_account=False), model)
        assert without[:-1] == with_account and len(without) == len(with_account) + 1
        assert without[-1].startswith("Conta não informada no CRM — preencha; isso não muda")
        assert all("Conta não informada" not in s for s in with_account)
    assert explain.explain_deal(row("Foque", has_account=False), model)[-1] == explain.NO_ACCOUNT_SENTENCE


def test_singular_and_last_day_wording():
    model = model_with()
    assert "janela boa por mais 1 dia." in explain.explain_deal(row("Foque", days_to_knot=1), model)[0]
    assert "último dia da janela boa" in explain.explain_deal(row("Foque", days_to_knot=0), model)[0]
    assert "falta 1 dia" in explain.explain_deal(row("Reative", days_to_limpe=1), model)[2]
    assert "último dia" in explain.explain_deal(row("Reative", days_to_limpe=0), model)[2]
    assert explain.explain_deal(row("Limpe", age_days=1), model)[0].startswith("Aberto há 1 dia ")


def test_a_chance_that_rounds_to_zero_is_shown_as_less_than_one_percent():
    sentences = explain.explain_deal(row("Reative", p_win=0.002), model_with())
    assert "para menos de 1%." in sentences[0] and "para 0%" not in sentences[0]


def test_explanation_uses_the_cut_model_not_a_global_one(deals):
    models = {T: score.fit_model(deals, T) for T in ("2017-06-30", "2017-09-30")}
    assert models["2017-06-30"].knot_days != models["2017-09-30"].knot_days
    for T, model in models.items():
        scored = score.score_deals(deals, T, model)
        deal = scored[scored["category"] == "Foque"].iloc[0]
        sentences = explain.explain_deal(deal, model)
        assert f"depois de {model.knot_days} dias" in sentences[2]
        assert f"{round(100 * deal['p_win'])}%" in sentences[1]
        lines = explain.how_it_works(model)
        assert f"até {model.knot_days} dias de idade" in lines[1]
        assert f"{len(model.curve.train_snapshots)} fotos" in lines[0]


def test_how_it_works_has_five_lines_with_the_model_numbers(today):
    model, _ = today
    lines = explain.how_it_works(model)
    assert len(lines) == 5
    assert "7 fotos mensais" in lines[0] and "31/03/2017 a 30/09/2017" in lines[0] and "13.100 casos" in lines[0]
    assert f"{round(100 * model.p_fresh)}% de chance" in lines[1] and f"até {model.knot_days} dias" in lines[1]
    assert "chance × preço de tabela" in lines[2] and "487 vezes" in lines[2]
    assert f"Foque: até {model.knot_days} dias" in lines[3] and f"Limpe: acima de {model.limpe_after_days} dias" in lines[3]
    assert "Vendedor não entra no score." in lines[4] and "ainda não foi rodado" in lines[4]
    assert not any(word in " ".join(lines).lower() for word in BANNED)


def test_how_it_works_fills_the_last_line_with_the_backtest_average(today):
    model, _ = today
    metrics = {"n_cortes": 4, "receita_score": 0.612, "receita_valor": 0.481, "receita_recencia": 0.298}
    last = explain.how_it_works(model, metrics)[4]
    assert last == (
        "Testado no passado em 4 datas: o top 20% do score capturou 61% da receita ganha depois, contra 48% "
        "ordenando por valor e 30% pelos mais recentes. Vendedor não entra no score."
    )


def test_how_it_works_handles_degenerate_curves():
    flat = explain.how_it_works(model_with(slope=0.0))
    assert "não muda com a idade" in flat[1]
    immediate = explain.how_it_works(model_with(knot=0))
    assert "desde o primeiro dia" in immediate[1]
    no_reative = explain.how_it_works(model_with(knot=138, limpe=138))
    assert "Reative: nenhum." in no_reative[3]
