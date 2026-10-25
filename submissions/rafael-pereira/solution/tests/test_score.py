"""Testes de `score.py`: logística, curva de idade, categorias, escala do score e garantias de justiça."""

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

from scorer import clean, config, features, score

SCORE_COLUMNS = ["opportunity_id", "age_days", "p_win", "expected_value", "score", "category",
                 "days_to_knot", "days_to_limpe"]
FACTS_AGE_BANDS = {"Foque": 126, "Reative": 172, "Limpe": 1291, "Qualifique": 500}  # protótipo do planejador


@pytest.fixture(scope="module")
def deals():
    return clean.load_deals()


@pytest.fixture(scope="module")
def today_model(deals):
    return score.fit_model(deals, config.DEFAULT_REFERENCE_DATE)


def fixed_model(knot=95, limpe=138, intercept=-0.41, slope=-2.59) -> score.ScoreModel:
    curve = score.AgeCurve(knot, intercept, slope, 0.33, 1000, ("2017-03-31",))
    return score.ScoreModel(curve, limpe, price_min=55.0, price_max=26768.0, as_of_date="2017-12-31")


def open_deals(ages, prices, T="2017-12-31") -> pd.DataFrame:
    """Deals Engaging abertos em T com as idades e os preços dados."""
    T = pd.Timestamp(T)
    df = pd.DataFrame({
        "opportunity_id": [f"D{i:03d}" for i in range(len(ages))],
        "deal_stage": "Engaging",
        "engage_date": [T - pd.Timedelta(days=int(a)) for a in ages],
        "close_date": pd.NaT,
        "close_value": np.nan,
        "sales_price": prices,
        "sales_agent": "Fulana",
        "product": "p",
        "account": "x",
    })
    return clean.add_derived(df, T)


# --- Logística ------------------------------------------------------------------------------------


def test_fit_logistic_reaches_a_zero_gradient():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(500), rng.normal(size=(500, 2))])
    y = (rng.random(500) < expit(X @ np.array([0.3, 1.0, -0.5]))).astype(float)
    for l2 in (0.0, 1.0):
        fit = score.fit_logistic(X, y, l2=l2)
        b = np.array(fit.coef)
        penalty = l2 * np.r_[0.0, b[1:]]  # o intercepto não é penalizado
        gradient = X.T @ (expit(X @ b) - y) + penalty
        assert np.abs(gradient).max() < 1e-4, (l2, gradient)


def test_fit_logistic_with_only_an_intercept_returns_the_logit_of_the_mean():
    y = np.array([1, 0, 0, 1, 1, 0, 0, 0], dtype=float)
    fit = score.fit_logistic(np.ones((8, 1)), y)
    assert fit.coef[0] == pytest.approx(np.log(0.375 / 0.625), abs=1e-6)


def test_l2_shrinks_the_coefficients_but_not_the_intercept_penalty():
    rng = np.random.default_rng(1)
    X = np.column_stack([np.ones(300), rng.normal(size=300)])
    y = (rng.random(300) < expit(2.0 * X[:, 1])).astype(float)
    free, shrunk = score.fit_logistic(X, y), score.fit_logistic(X, y, l2=50.0)
    assert abs(shrunk.coef[1]) < abs(free.coef[1])


def test_bounds_keep_the_slope_from_turning_positive():
    age = np.arange(200, dtype=float)
    y = (age >= 100).astype(float)  # os mais velhos ganham: o ajuste livre teria inclinação positiva
    X = score.age_design(age, knot=0)
    assert score.fit_logistic(X, y).coef[1] > 0
    assert score.fit_logistic(X, y, bounds=[(None, None), (None, 0.0)]).coef[1] == pytest.approx(0.0, abs=1e-9)


# --- Curva de idade -------------------------------------------------------------------------------


def test_p_is_monotonic_non_increasing_and_positive_up_to_500_days(today_model):
    ages = np.arange(0, 501)
    for model in (today_model, fixed_model(knot=0, slope=-0.4), fixed_model(knot=60)):
        p = model.curve.p_win(ages)
        assert (np.diff(p) <= 1e-15).all()
        assert (p > 0).all()
        assert model.curve.p_win(400) > 0
    assert today_model.curve.p_win(0) == today_model.curve.p_win(today_model.knot_days) == today_model.p_fresh


def test_p_win_accepts_scalars_and_arrays():
    curve = fixed_model().curve
    assert isinstance(curve.p_win(10), float)
    assert curve.p_win(np.array([10, 200])).shape == (2,)


def test_fit_recovers_the_knot_on_synthetic_data():
    rng = np.random.default_rng(7)
    age = rng.uniform(0, 300, 30000)
    p = expit(-0.4 + -2.5 * np.maximum(0, age - 60) / 30)
    y = (rng.random(len(age)) < p).astype(float)
    knot, fit = score.fit_age_curve(age, y)
    assert abs(knot - 60) <= 10
    assert fit.coef[0] == pytest.approx(-0.4, abs=0.1)
    assert fit.coef[1] < 0


def test_ties_pick_the_smallest_knot():
    age = np.arange(200, dtype=float)
    y = (age >= 100).astype(float)  # inclinação travada em 0: todos os joelhos empatam
    knot, fit = score.fit_age_curve(age, y)
    assert knot == 0 and fit.coef[1] == pytest.approx(0.0, abs=1e-9)


def test_halving_days_is_where_the_chance_is_half_of_the_plateau():
    curve = fixed_model().curve
    halfway = curve.knot_days + curve.halving_days
    assert curve.p_win(halfway) == pytest.approx(curve.p_fresh / 2, rel=1e-9)
    flat = score.AgeCurve(50, -0.4, 0.0, 0.4, 10, ("2017-03-31",))
    assert flat.halving_days is None


def test_fit_matches_the_planner_prototype_within_tolerance(deals):
    prototype_knots = {"2017-06-30": 70, "2017-07-31": 100, "2017-08-31": 95, "2017-09-30": 90}
    for T, expected in prototype_knots.items():
        model = score.fit_model(deals, T)
        assert abs(model.knot_days - expected) <= 5, (T, model.knot_days)
        assert model.curve.slope_per_30d < 0
    today = score.fit_model(deals, config.DEFAULT_REFERENCE_DATE)
    assert abs(today.knot_days - 95) <= 5
    assert today.curve.intercept == pytest.approx(-0.41, abs=0.1) and today.p_fresh == pytest.approx(0.40, abs=0.02)
    assert today.curve.slope_per_30d == pytest.approx(-2.59, abs=0.3)
    assert today.limpe_after_days == 138
    assert len(today.curve.train_snapshots) == 7 and abs(today.curve.train_rows - 13100) <= 262


# --- Limite de Limpe, preços e escala -------------------------------------------------------------


def test_limpe_limit_comes_from_wins_closed_up_to_T(deals):
    T = pd.Timestamp("2017-06-30")
    won = deals[(deals["deal_stage"] == "Won") & (deals["close_date"] <= T)]
    expected = int((won["close_date"] - won["engage_date"]).dt.days.max())
    assert score.fit_model(deals, T).limpe_after_days == max(expected, score.fit_model(deals, T).knot_days)
    # um ganho enorme que só acontece depois de T não pode mexer no limite
    late = deals.iloc[[0]].assign(
        opportunity_id="LATE", deal_stage="Won", engage_date=pd.Timestamp("2017-01-15"),
        close_date=pd.Timestamp("2017-08-15"), close_value=100.0,
    )
    with_late = pd.concat([deals, late], ignore_index=True)
    assert score.fit_model(with_late, T).limpe_after_days == score.fit_model(deals, T).limpe_after_days
    assert score.fit_model(with_late, "2017-09-30").limpe_after_days > 200  # em 30/09 o ganho já existe


def test_limpe_limit_is_never_below_the_knot():
    assert score.limpe_limit(pd.Series([10.0, 40.0]), knot=95) == 95
    assert score.limpe_limit(pd.Series([10.0, 138.0]), knot=95) == 138
    # com limite igual ao joelho, a lista Reative fica vazia
    scored = score.score_deals(open_deals([50, 95, 96, 300], 4821), "2017-12-31", fixed_model(knot=95, limpe=95))
    assert scored["category"].tolist() == ["Foque", "Foque", "Limpe", "Limpe"]


def test_price_range_matches_the_catalog(deals, today_model):
    catalog = pd.read_csv(config.RAW_DIR / "products.csv", encoding="utf-8")
    assert today_model.price_min == catalog["sales_price"].min() == 55
    assert today_model.price_max == catalog["sales_price"].max() == 26768
    assert today_model.price_max / today_model.price_min == pytest.approx(486.69, abs=0.01)


def test_each_product_has_a_single_list_price(deals):
    assert (deals.groupby("product")["sales_price"].nunique() == 1).all()


def test_score_is_integer_in_range_and_a_new_deal_of_the_priciest_product_gets_100(deals, today_model):
    scored = score.score_deals(deals, config.DEFAULT_REFERENCE_DATE, today_model)
    assert scored["score"].between(0, 100).all() and scored["score"].dtype == "Int64"
    fresh = score.score_deals(open_deals([0, 0, 0], [55, 4821, 26768]), "2017-12-31", fixed_model())
    assert fresh["score"].tolist() == [round(100 * np.log1p(1) / np.log1p(26768 / 55)), fresh["score"][1], 100]
    assert 0 < fresh["score"][0] < fresh["score"][1] < 100


def test_score_is_monotonic_in_expected_value():
    ages = np.tile(np.arange(0, 200, 4), 3)
    prices = np.repeat([55, 4821, 26768], 50)
    scored = score.score_deals(open_deals(ages, prices), "2017-12-31", fixed_model())
    ordered = scored.sort_values("expected_value")
    assert (ordered["score"].diff().dropna() >= 0).all()
    assert scored["score"].min() == 0 and scored["score"].max() == 100


def test_an_old_expensive_deal_scores_below_a_fresh_cheap_one_only_when_expected_value_says_so():
    scored = score.score_deals(open_deals([300, 0], [26768, 4821]), "2017-12-31", fixed_model())
    assert scored["expected_value"][0] < scored["expected_value"][1]
    assert scored["score"][0] < scored["score"][1]


# --- Categorias -----------------------------------------------------------------------------------


def test_category_boundaries_and_deadlines():
    ages = [0, 94, 95, 96, 137, 138, 139, 400]
    scored = score.score_deals(open_deals(ages, 4821), "2017-12-31", fixed_model(knot=95, limpe=138))
    assert scored["category"].tolist() == ["Foque", "Foque", "Foque", "Reative", "Reative", "Reative", "Limpe", "Limpe"]
    assert scored["days_to_knot"].tolist()[:4] == [95, 1, 0, pd.NA]
    assert scored["days_to_limpe"].tolist()[:6] == [138, 44, 43, 42, 1, 0]
    assert scored["days_to_knot"][4:].isna().all() and scored["days_to_limpe"][6:].isna().all()


def test_today_category_counts_match_the_prototype(deals, today_model):
    scored = score.score_deals(deals, config.DEFAULT_REFERENCE_DATE, today_model, include_prospecting=True)
    counts = scored["category"].value_counts().to_dict()
    for category, expected in FACTS_AGE_BANDS.items():
        assert abs(counts[category] - expected) <= 0.02 * expected, (category, counts)
    limpe_value = scored.loc[scored["category"] == "Limpe", "sales_price"].sum()
    assert limpe_value == 3198664  # o mesmo número do facts.json (zumbis acima de 138 dias)


# --- Justiça e vazamento pela conta ---------------------------------------------------------------


def _same_scores(a: pd.DataFrame, b: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(
        a[SCORE_COLUMNS].sort_values("opportunity_id").reset_index(drop=True),
        b[SCORE_COLUMNS].sort_values("opportunity_id").reset_index(drop=True),
    )


@pytest.mark.parametrize("T", ["2017-06-30", "2017-12-31"])
def test_permuting_sales_agent_changes_no_score(deals, T):
    rng = np.random.default_rng(3)
    shuffled = deals.copy()
    for column in ("sales_agent", "manager", "regional_office"):
        shuffled[column] = rng.permutation(deals[column].to_numpy())
    assert (shuffled["sales_agent"] != deals["sales_agent"]).mean() > 0.9
    model, model_shuffled = score.fit_model(deals, T), score.fit_model(shuffled, T)
    assert model == model_shuffled
    _same_scores(score.score_deals(deals, T, model), score.score_deals(shuffled, T, model_shuffled))


def test_account_columns_do_not_change_the_model_or_scores(deals):
    T = "2017-09-30"
    rng = np.random.default_rng(4)
    changed = deals.copy()
    changed["has_account"] = rng.random(len(deals)) < 0.5  # inverte a relação "sem conta = nunca fechou"
    changed["sector"] = rng.permutation(deals["sector"].to_numpy())
    changed["employees"] = rng.permutation(deals["employees"].to_numpy())
    changed.loc[changed["has_account"], "account"] = np.nan
    assert (changed["has_account"] != deals["has_account"]).sum() > 1000
    model, model_changed = score.fit_model(deals, T), score.fit_model(changed, T)
    assert model == model_changed
    _same_scores(score.score_deals(deals, T, model), score.score_deals(changed, T, model_changed))


def test_close_value_is_never_read(deals):
    T = "2017-09-30"
    rng = np.random.default_rng(5)
    changed = deals.assign(close_value=rng.uniform(0, 1e6, len(deals)))
    assert score.fit_model(deals, T) == score.fit_model(changed, T)
    _same_scores(
        score.score_deals(deals, T, score.fit_model(deals, T)),
        score.score_deals(changed, T, score.fit_model(changed, T)),
    )


def test_fit_and_score_do_not_modify_their_input(deals):
    before = deals.copy(deep=True)
    model = score.fit_model(deals, "2017-09-30")
    score.score_deals(deals, "2017-09-30", model)
    pd.testing.assert_frame_equal(before, deals)


def test_cli_prints_the_model_table_and_the_lists(capsys):
    assert score.main() == 0
    out = capsys.readouterr().out
    assert "2017-06-30" in out and "2017-12-31" in out
    assert "Foque" in out and "Limpe" in out and "1.291" in out


def test_score_deals_refuses_a_model_fitted_after_T(deals, today_model):
    with pytest.raises(AssertionError):
        score.score_deals(deals, "2017-06-30", today_model)


# --- Prospecting e ordenação ----------------------------------------------------------------------


def test_prospecting_is_only_scored_when_asked_and_never_gets_a_score(deals, today_model):
    plain = score.score_deals(deals, config.DEFAULT_REFERENCE_DATE, today_model)
    assert "Qualifique" not in set(plain["category"]) and (plain["deal_stage"] == "Engaging").all()
    full = score.score_deals(deals, config.DEFAULT_REFERENCE_DATE, today_model, include_prospecting=True)
    qualifique = full[full["category"] == "Qualifique"]
    assert len(qualifique) == 500 and (qualifique["deal_stage"] == "Prospecting").all()
    assert qualifique[["p_win", "expected_value", "score", "age_days", "days_to_knot", "days_to_limpe"]].isna().all().all()
    assert full.loc[full["category"] != "Qualifique", "score"].notna().all()
    with pytest.raises(AssertionError):  # num corte do passado Prospecting não existe
        score.score_deals(deals, "2017-06-30", score.fit_model(deals, "2017-06-30"), include_prospecting=True)


def test_order_for_list_follows_the_rules_of_each_list():
    ages = [10, 10, 50, 120, 120, 300, 200, 200]
    prices = [4821, 4821, 55, 4821, 26768, 3393, 3393, 26768]
    deals = open_deals(ages, prices)
    scored = score.score_deals(deals, "2017-12-31", fixed_model(knot=95, limpe=138))
    prospecting = pd.DataFrame({"opportunity_id": ["P1", "P2"], "deal_stage": "Prospecting", "sales_price": [100, 900],
                                "category": "Qualifique"})
    ordered = score.order_for_list(pd.concat([scored, prospecting], ignore_index=True))
    assert ordered["category"].tolist() == ["Foque"] * 3 + ["Reative"] * 2 + ["Limpe"] * 3 + ["Qualifique"] * 2
    ids = ordered["opportunity_id"].tolist()
    assert ids[:3] == ["D000", "D001", "D002"]  # mesmo valor esperado: desempate por id; o barato por último
    assert ids[3:5] == ["D004", "D003"]  # Reative: valor esperado desc (o de 26.768 vence)
    assert ids[5:8] == ["D007", "D005", "D006"]  # Limpe: preço desc, depois idade desc (300 antes de 200)
    assert ids[8:] == ["P2", "P1"]  # Qualifique: preço desc
