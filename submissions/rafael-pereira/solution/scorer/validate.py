"""Validação do Lead Scorer: métricas, backtest temporal e relatório.

Duas camadas no mesmo módulo:

1. Primitivas de métrica (funções puras, numpy/scipy; bloco 3a.2): AUC, captura no top 20%, baseline
   aleatório, bootstrap das diferenças, Brier, log-loss e `beats` (o helper do critério pré-registrado).
2. Backtest (bloco 3b): `evaluate_cut`, `check_criterion`, o ajuste único pré-definido (curva em faixas
   de 15 dias com PAVA), o teste de atributos, as auditorias e `run_backtest`, que grava
   `data/processed/backtest_metrics.json` e `backtest_tables.md`.

Uso: `python -m scorer.validate` (imprime a tabela principal e PASSOU/FALHOU).
Tudo é determinístico: sementes fixas, sem `now()`.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata

from . import config, features
from .score import FitConfig, LogisticFit, age_design, fit_model, score_deals

# Folga numérica para a comparação do critério: 0,61 - 0,60 vale 0,010000000000000009 em ponto
# flutuante e, sem folga, passaria como "mais de 0,01".
_FLOAT_EPS = 1e-12
_PROB_CLIP = 1e-12


def _vec(x, name: str) -> np.ndarray:
    """Converte para vetor float 1-D."""
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} deve ser unidimensional (recebeu {arr.ndim} dimensões)")
    return arr


def _pair(a, b, name_a: str, name_b: str) -> tuple[np.ndarray, np.ndarray]:
    va, vb = _vec(a, name_a), _vec(b, name_b)
    if len(va) != len(vb):
        raise ValueError(f"{name_a} e {name_b} têm tamanhos diferentes ({len(va)} e {len(vb)})")
    return va, vb


# --- AUC e captura no topo -----------------------------------------------------------------
def auc(score, y) -> float:
    """AUC por Mann-Whitney com posto médio: 1 = ordem perfeita, 0,5 = sem poder, 0 = invertida.

    `y` é binário (0/1 ou bool). Com uma classe só, a AUC não existe: devolve NaN.
    """
    s, yv = _pair(score, y, "score", "y")
    pos = yv != 0
    n1 = int(pos.sum())
    n0 = len(yv) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = rankdata(s)  # método "average": empates recebem o posto médio
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def top_share(score, gain, frac: float = config.TOP_FRAC) -> float:
    """Fração do total de `gain` capturada pelo top `frac` do `score` (por contagem, K = frac*n).

    Ordena o score de forma decrescente. Empates são tratados pelo valor esperado sob desempate
    aleatório: cada grupo de valores iguais entra inteiro se cabe em K; o grupo que cruza K entra
    na fração (K - acumulado)/tamanho do grupo, levando essa fração do ganho do grupo.
    Total de `gain` igual a zero (ou nenhum deal): NaN.

    Com `gain` = y binário é a "captura de ganhos"; com `gain` = close_value dos Won (0 nos
    demais) é a "receita capturada".
    """
    s, g = _pair(score, gain, "score", "gain")
    n = len(s)
    total = g.sum()
    if n == 0 or total == 0:
        return float("nan")
    k = frac * n
    _, inverse, counts = np.unique(s, return_inverse=True, return_counts=True)
    group_gain = np.bincount(inverse.ravel(), weights=g, minlength=len(counts))
    counts = counts[::-1]  # np.unique ordena de forma crescente; queremos do maior score ao menor
    group_gain = group_gain[::-1]
    before = np.cumsum(counts) - counts
    taken = np.clip((k - before) / counts, 0.0, 1.0)
    return float((taken * group_gain).sum() / total)


# --- Baseline aleatório e bootstrap ----------------------------------------------------------
def _summary(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(arr.mean()),
        "p5": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
    }


def random_baseline(
    gain,
    y,
    n_seeds: int = config.RANDOM_SEEDS,
    frac: float = config.TOP_FRAC,
) -> dict:
    """Baseline aleatório: scores sorteados com sementes 0..n_seeds-1 (`default_rng(seed)`).

    `gain` é o ganho monetário (close_value dos Won, 0 nos demais) e `y` o desfecho binário.
    Para cada sorteio calcula a AUC, a captura de ganhos (top_share com gain = y) e a receita
    capturada (top_share com gain = `gain`) no top `frac`.

    Devolve {"auc": ..., "capture": ..., "revenue": ...}, cada um com "mean", "p5" e "p95"
    sobre os sorteios.
    """
    g, yv = _pair(gain, y, "gain", "y")
    y_gain = (yv != 0).astype(float)
    n = len(g)
    aucs, captures, revenues = [], [], []
    for seed in range(n_seeds):
        rnd = np.random.default_rng(seed).random(n)
        aucs.append(auc(rnd, yv))
        captures.append(top_share(rnd, y_gain, frac))
        revenues.append(top_share(rnd, g, frac))
    return {"auc": _summary(aucs), "capture": _summary(captures), "revenue": _summary(revenues)}


def bootstrap_diff(
    score_a,
    score_b,
    gain,
    reps: int = config.BOOTSTRAP_REPS,
    seed: int = 0,
    frac: float = config.TOP_FRAC,
) -> dict:
    """Diferença `top_share(a) - top_share(b)` com IC de 2,5% a 97,5% por bootstrap.

    Reamostra os deals com reposição, com os mesmos índices para os dois métodos (pareado).
    Reamostras sem ganho total (top_share indefinido) são descartadas do IC; "n_valid" diz
    quantas sobraram.

    Devolve {"diff": observada, "ci_low": ..., "ci_high": ..., "n_valid": ...}.
    """
    a, b = _pair(score_a, score_b, "score_a", "score_b")
    g = _vec(gain, "gain")
    if len(g) != len(a):
        raise ValueError(f"gain tem tamanho diferente de score_a ({len(g)} e {len(a)})")
    n = len(a)
    diff = top_share(a, g, frac) - top_share(b, g, frac)
    rng = np.random.default_rng(seed)
    diffs = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, n)
        diffs[i] = top_share(a[idx], g[idx], frac) - top_share(b[idx], g[idx], frac)
    valid = diffs[~np.isnan(diffs)]
    if len(valid) == 0:
        lo = hi = float("nan")
    else:
        lo, hi = (float(v) for v in np.percentile(valid, [2.5, 97.5]))
    return {"diff": float(diff), "ci_low": lo, "ci_high": hi, "n_valid": int(len(valid))}


# --- Calibração ----------------------------------------------------------------------------
def brier(p, y) -> float:
    """Erro quadrático médio entre a probabilidade `p` e o desfecho binário `y` (menor é melhor)."""
    pv, yv = _pair(p, y, "p", "y")
    if len(pv) == 0:
        return float("nan")
    return float(np.mean((pv - (yv != 0)) ** 2))


def log_loss(p, y) -> float:
    """Log-loss médio (natural); `p` é cortada em [1e-12, 1 - 1e-12] para evitar log(0)."""
    pv, yv = _pair(p, y, "p", "y")
    if len(pv) == 0:
        return float("nan")
    pc = np.clip(pv, _PROB_CLIP, 1 - _PROB_CLIP)
    pos = yv != 0
    return float(-np.mean(np.where(pos, np.log(pc), np.log1p(-pc))))


# --- Critério pré-registrado -----------------------------------------------------------------
def beats(score_value: float, others, tie_tol: float = 0.01) -> bool:
    """True só se `score_value` supera CADA valor de `others` por mais de `tie_tol`.

    Diferença menor ou igual a `tie_tol` é empate, e empate não bate. NaN em qualquer lado não
    bate. `others` vazio é erro (um critério sem baselines passaria sem provar nada).
    """
    values = [float(v) for v in others]
    if not values:
        raise ValueError("beats exige ao menos um valor em `others`")
    return all(float(score_value) - v - tie_tol > _FLOAT_EPS for v in values)


# =============================================================================================
# Backtest (bloco 3b)
# =============================================================================================
METHOD_LABELS = {
    "score": "Score (valor esperado)",
    "p_only": "Só a chance (diagnóstico)",
    "valor": "Ordenar por valor",
    "recencia": "Mais recentes primeiro",
    "aleatorio": "Aleatório (média de sorteios)",
}
BASELINES = ("valor", "recencia", "aleatorio")
METRIC_KEYS = ("auc", "ganhos_top20", "receita_top20")
PRIMARY_METRIC = "receita_top20"
SIZE_LABELS = ("pequena", "média", "grande")
CALIBRATION_BANDS = ((0, 30), (31, 60), (61, 90), (91, 120), (121, 150), (151, None))
RULE_TEXT = (
    "O score vence se, nos 4 cortes, a receita capturada no top 20% for maior que a de ordenar por valor, "
    "maior que a de ordenar pelos mais recentes e maior que a média e o percentil 95 de 200 sorteios "
    "aleatórios. Diferença de até 1 ponto percentual é empate, e empate não vence."
)


def _py(obj):
    """Converte para tipos Python puros (NaN vira None), pronto para `json.dump`."""
    if isinstance(obj, dict):
        return {str(k): _py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_py(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return None if math.isnan(float(obj)) else float(obj)
    if obj is pd.NA or obj is pd.NaT:
        return None
    return obj


def _band_label(lo, hi) -> str:
    return f"{lo} dias ou mais" if hi is None else f"{lo} a {hi} dias"


def _band_mask(age: np.ndarray, lo, hi) -> np.ndarray:
    return (age >= lo) if hi is None else ((age >= lo) & (age <= hi))


def _mean_or_none(values) -> float | None:
    return float(np.mean(values)) if len(values) else None


# --- curva em faixas (ajuste único pré-definido) -----------------------------------------------
def pava_nonincreasing(values, weights) -> np.ndarray:
    """Regressão isotônica não crescente por PAVA (blocos adjacentes que sobem são fundidos pela média ponderada)."""
    blocks: list[list[float]] = []  # [média, peso, quantos]
    for value, weight in zip(values, weights):
        blocks.append([float(value), float(weight), 1])
        while len(blocks) > 1 and blocks[-2][0] < blocks[-1][0]:
            m2, w2, c2 = blocks.pop()
            m1, w1, c1 = blocks.pop()
            blocks.append([(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    out: list[float] = []
    for mean, _, count in blocks:
        out += [mean] * int(count)
    return np.asarray(out)


@dataclass(frozen=True)
class BinnedCurve:
    """Chance por idade em faixas, interpolada linearmente entre os pontos médios das faixas."""

    midpoints: tuple[float, ...]
    rates: tuple[float, ...]  # já suavizada (pseudo-contagem) e não crescente (PAVA)
    counts: tuple[int, ...]
    base_rate: float

    def p_win(self, age):
        age_arr = np.asarray(age, dtype="float64")
        p = np.interp(age_arr, self.midpoints, self.rates)
        return float(p) if p.ndim == 0 else p


def fit_binned_curve(
    age, y, width: int = config.ADJUST_BIN_DAYS, alpha: float = config.ADJUST_PSEUDO_COUNT
) -> BinnedCurve:
    """Faixas de `width` dias; taxa = (ganhos + alpha*base)/(n + alpha); PAVA com pesos n + alpha.

    Faixas sem nenhum caso são descartadas (a interpolação passa por cima delas).
    """
    age = np.asarray(age, dtype="float64")
    y = np.asarray(y, dtype="float64")
    base = float(y.mean())
    idx = (age // width).astype(int)
    size = int(idx.max()) + 1
    n = np.bincount(idx, minlength=size)
    wins = np.bincount(idx, weights=y, minlength=size)
    keep = n > 0
    rate = (wins[keep] + alpha * base) / (n[keep] + alpha)
    iso = pava_nonincreasing(rate, n[keep] + alpha)
    mids = (np.arange(size) * width + width / 2)[keep]
    return BinnedCurve(tuple(float(m) for m in mids), tuple(float(r) for r in iso), tuple(int(c) for c in n[keep]), base)


# --- logística com penalização seletiva (teste de atributos) -----------------------------------
def fit_logistic_masked(X, y, l2: float, penalized, bounds=None) -> LogisticFit:
    """Como `score.fit_logistic`, mas o L2 vale só para as colunas listadas em `penalized`.

    Com `penalized` = todas as colunas menos o intercepto, dá o mesmo resultado de `fit_logistic(l2=l2)`.
    """
    X = np.asarray(X, dtype="float64")
    y = np.asarray(y, dtype="float64")
    pen = np.zeros(X.shape[1])
    pen[list(penalized)] = 1.0

    def nll_and_grad(b):
        z = X @ b
        nll = np.logaddexp(0.0, z).sum() - y @ z + 0.5 * l2 * np.sum((b * pen) ** 2)
        return nll, X.T @ (expit(z) - y) + l2 * b * pen

    start = np.zeros(X.shape[1])
    base = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
    start[0] = math.log(base / (1 - base))
    result = minimize(
        nll_and_grad, start, jac=True, method="L-BFGS-B", bounds=bounds,
        options={"ftol": 1e-13, "gtol": 1e-9, "maxiter": 1000},
    )
    return LogisticFit(coef=tuple(float(c) for c in result.x), nll=float(result.fun))


# --- um corte: ajuste, população e desfecho ------------------------------------------------------
@dataclass
class _Cut:
    T: pd.Timestamp
    cfg: FitConfig
    kind: str
    model: object
    p_fn: Callable
    train: pd.DataFrame
    pop: pd.DataFrame
    curve: object | None = None


def _population(deals: pd.DataFrame, T: pd.Timestamp, model, cfg: FitConfig) -> pd.DataFrame:
    """Engaging abertos em T (zumbis incluídos) com o desfecho vindo dos dados completos.

    `y`: ganho até o fim dos dados; `gain`: close_value dos ganhos (0 nos demais); `y_h`: ganho até T + H;
    `resolved`: o deal fechou (Won ou Lost) até o fim dos dados.
    """
    scored = score_deals(deals, T, model)
    outcome = deals[["opportunity_id", "deal_stage", "close_date", "close_value"]].rename(
        columns={"deal_stage": "final_stage", "close_date": "final_close_date", "close_value": "final_close_value"}
    )
    pop = scored.merge(outcome, on="opportunity_id", how="left", validate="one_to_one")
    assert len(pop) == len(scored)
    won = pop["final_stage"].eq("Won")
    horizon_end = T + pd.Timedelta(days=cfg.horizon_days)
    pop["y"] = won.astype("int64")
    pop["gain"] = np.where(won, pop["final_close_value"], 0.0)
    pop["y_h"] = (won & (pop["final_close_date"] <= horizon_end)).astype("int64")
    pop["resolved"] = pop["final_stage"].isin(config.CLOSED_STAGES)
    return pop


def _build_cut(deals: pd.DataFrame, T, cfg: FitConfig | None = None, kind: str = "plateau") -> _Cut:
    cfg = cfg or FitConfig()
    T = pd.Timestamp(T)
    model = fit_model(deals, T, cfg)
    train = features.training_set(features.as_of(deals, T), T, cfg.horizon_days, cfg.first_snapshot)
    pop = _population(deals, T, model, cfg)
    age = pop["age_days"].to_numpy(dtype="float64")
    curve = None
    if kind == "plateau":
        p_fn = model.curve.p_win
        assert np.allclose(p_fn(age), pop["p_win"].to_numpy(dtype="float64")), "p_win do score_deals difere da curva"
    elif kind == "binned":
        curve = fit_binned_curve(train["age_days"], train["y"])
        p_fn = curve.p_win
    else:
        raise ValueError(f"curva desconhecida: {kind}")
    return _Cut(T, cfg, kind, model, p_fn, train, pop, curve)


def _mm(score_vec, y, gain) -> dict:
    """Os três números de um método: AUC, captura de ganhos e receita capturada no top 20%."""
    yf = np.asarray(y, dtype=float)
    return {"auc": auc(score_vec, yf), "ganhos_top20": top_share(score_vec, yf), "receita_top20": top_share(score_vec, gain)}


def _random_block(gain, y) -> dict:
    rb = random_baseline(gain, y)
    mapping = {"auc": "auc", "ganhos_top20": "capture", "receita_top20": "revenue"}
    out = {k: rb[v]["mean"] for k, v in mapping.items()}
    out["p5"] = {k: rb[v]["p5"] for k, v in mapping.items()}
    out["p95"] = {k: rb[v]["p95"] for k, v in mapping.items()}
    return out


def _model_dict(model) -> dict:
    curve = model.curve
    return {
        "as_of": model.as_of_date,
        "horizon_days": model.horizon_days,
        "knot_days": curve.knot_days,
        "p_fresh": curve.p_fresh,
        "intercept": curve.intercept,
        "slope_per_30d": curve.slope_per_30d,
        "halving_days": curve.halving_days,
        "limpe_after_days": model.limpe_after_days,
        "train_rows": curve.train_rows,
        "train_snapshots": list(curve.train_snapshots),
        "n_snapshots": len(curve.train_snapshots),
        "base_rate": curve.base_rate,
    }


def _prop_diff_ci(a, b, reps: int = config.BOOTSTRAP_REPS, seed: int = 0) -> dict:
    """Diferença de taxas (b - a) com IC 2,5%-97,5% por bootstrap (cada grupo reamostrado à parte)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) == 0 or len(b) == 0:
        return {"diff": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    diffs = np.empty(reps)
    for i in range(reps):
        diffs[i] = b[rng.integers(0, len(b), len(b))].mean() - a[rng.integers(0, len(a), len(a))].mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"diff": float(b.mean() - a.mean()), "ci_low": float(lo), "ci_high": float(hi)}


def _foque_by_age(c: _Cut) -> dict:
    """Dentro do Foque do corte: a chance cai com a idade? (risco levantado na 3a para fins de trimestre)."""
    foque = c.pop.loc[c.pop["category"] == "Foque"]
    age = foque["age_days"].to_numpy(dtype=float)
    yh = foque["y_h"].to_numpy(dtype=float)
    y = foque["y"].to_numpy(dtype=float)
    p = c.p_fn(age)
    rows, masks = [], []
    for lo, hi in config.FOQUE_AGE_BANDS:
        m = _band_mask(age, lo, hi)
        masks.append(m)
        rows.append({
            "faixa": _band_label(lo, hi), "idade_min": lo, "idade_max": hi, "n": int(m.sum()),
            "p_modelo": _mean_or_none(p[m]), "taxa_ganho_90d": _mean_or_none(yh[m]), "taxa_ganho_final": _mean_or_none(y[m]),
        })
    first, last = masks[0], masks[-1]
    return {
        "n_foque": int(len(foque)),
        "faixas": rows,
        "diferenca_ultima_menos_primeira_90d": _prop_diff_ci(yh[first], yh[last]),
    }


def _calibration(c: _Cut) -> list[dict]:
    pop = c.pop
    age = pop["age_days"].to_numpy(dtype=float)
    p = c.p_fn(age)
    yh = pop["y_h"].to_numpy(dtype=float)
    rows = []
    for lo, hi in CALIBRATION_BANDS:
        m = _band_mask(age, lo, hi)
        rows.append({
            "faixa": _band_label(lo, hi), "idade_min": lo, "idade_max": hi, "n": int(m.sum()),
            "p_modelo": _mean_or_none(p[m]), "taxa_observada_90d": _mean_or_none(yh[m]),
        })
    return rows


def _categories(c: _Cut) -> dict:
    pop = c.pop
    total_gain = float(pop["gain"].sum())
    out = {}
    for cat in ("Foque", "Reative", "Limpe"):
        part = pop.loc[pop["category"] == cat]
        gain = float(part["gain"].sum())
        out[cat] = {
            "n": int(len(part)),
            "ganhos": int(part["y"].sum()),
            "pct_ganhos": _mean_or_none(part["y"].to_numpy(dtype=float)),
            "receita_ganha": gain,
            "pct_receita": gain / total_gain if total_gain else None,
            "valor_tabela": float(part["sales_price"].sum()),
            "valor_esperado": float(c.p_fn(part["age_days"].to_numpy(dtype=float)) @ part["sales_price"].to_numpy(dtype=float)),
        }
    return out


def _resolved(c: _Cut, vecs: dict) -> dict:
    """Sensibilidade "só resolvidos": tira os deals ainda abertos em 31/12/2017 (censura à direita)."""
    pop = c.pop
    res = pop["resolved"].to_numpy(dtype=bool)
    ref = pd.Timestamp(config.DEFAULT_REFERENCE_DATE)
    open_age_at_ref = (ref - pop.loc[~pop["resolved"], "engage_date"]).dt.days
    y, gain = pop["y"].to_numpy()[res], pop["gain"].to_numpy(dtype=float)[res]
    out = {
        "n_abertos_em_t": int(len(pop)),
        "n_resolvidos": int(res.sum()),
        "n_abertos_em_31_12": int((~res).sum()),
        "n_abertos_em_31_12_que_ainda_podem_fechar": int((open_age_at_ref <= c.model.limpe_after_days).sum()),
        "metodos": {m: _mm(vecs[m][res], y, gain) for m in ("score", "valor", "recencia")},
    }
    out["metodos"]["aleatorio"] = _random_block(gain, y)
    return out


def evaluate_cut(deals: pd.DataFrame, T, cfg: FitConfig | None = None, curve_kind: str = "plateau") -> dict:
    """Todas as métricas de um corte T (modelo ajustado só com dados até T; desfecho dos dados completos)."""
    return _evaluate(_build_cut(deals, T, cfg, curve_kind))


def _vectors(c: _Cut) -> dict:
    price = c.pop["sales_price"].to_numpy(dtype=float)
    age = c.pop["age_days"].to_numpy(dtype=float)
    p = c.p_fn(age)
    return {"score": p * price, "p_only": p, "valor": price, "recencia": -age}


def _evaluate(c: _Cut) -> dict:
    pop = c.pop
    y = pop["y"].to_numpy(dtype=int)
    gain = pop["gain"].to_numpy(dtype=float)
    yh = pop["y_h"].to_numpy(dtype=float)
    vecs = _vectors(c)
    metodos = {m: _mm(v, y, gain) for m, v in vecs.items()}
    metodos["aleatorio"] = _random_block(gain, y)
    p = vecs["p_only"]
    base = c.model.curve.base_rate
    constant = np.full(len(yh), base)
    return {
        "cut": c.T.strftime("%Y-%m-%d"),
        "curva": c.kind,
        "modelo": _model_dict(c.model),
        "modelo_faixas": None if c.curve is None else {
            "pontos_medios": list(c.curve.midpoints), "taxas": list(c.curve.rates), "casos": list(c.curve.counts)
        },
        "populacao": {
            "n": int(len(pop)), "ganhos": int(y.sum()), "pct_ganhos": float(y.mean()),
            "receita_ganha": float(gain.sum()), "ganhos_em_90d": int(yh.sum()), "pct_ganhos_em_90d": float(yh.mean()),
            "valor_tabela": float(pop["sales_price"].sum()),
        },
        "metodos": metodos,
        "brier": {
            "modelo": brier(p, yh), "constante": brier(constant, yh),
            "log_loss_modelo": log_loss(p, yh), "log_loss_constante": log_loss(constant, yh), "n": int(len(yh)),
        },
        "bootstrap": {
            "score_menos_valor": bootstrap_diff(vecs["score"], vecs["valor"], gain),
            "score_menos_recencia": bootstrap_diff(vecs["score"], vecs["recencia"], gain),
        },
        "categorias": _categories(c),
        "calibracao": _calibration(c),
        "resolvidos": _resolved(c, vecs),
        "foque_por_idade": _foque_by_age(c),
    }


# --- critério pré-registrado ---------------------------------------------------------------------
def check_criterion(cuts: list[dict], tie_tol: float = config.CRITERION_TIE_TOL) -> dict:
    """Aplica o critério às métricas dos cortes (as mesmas chaves de `evaluate_cut`). Passa só se todos passarem."""
    per_cut = []
    for c in cuts:
        m = c["metodos"]
        s = m["score"][PRIMARY_METRIC]
        rnd = m["aleatorio"]
        checks = {
            "bate_valor": beats(s, [m["valor"][PRIMARY_METRIC]], tie_tol),
            "bate_recencia": beats(s, [m["recencia"][PRIMARY_METRIC]], tie_tol),
            "bate_aleatorio_media": beats(s, [rnd[PRIMARY_METRIC]], tie_tol),
            "bate_aleatorio_p95": beats(s, [rnd["p95"][PRIMARY_METRIC]], tie_tol),
        }
        per_cut.append({
            "cut": c["cut"], "score": s, "valor": m["valor"][PRIMARY_METRIC], "recencia": m["recencia"][PRIMARY_METRIC],
            "aleatorio_media": rnd[PRIMARY_METRIC], "aleatorio_p95": rnd["p95"][PRIMARY_METRIC],
            **checks, "passa": all(checks.values()),
        })
    return {"passed": bool(per_cut) and all(r["passa"] for r in per_cut), "per_cut": per_cut}


def _mean_metrics(cuts: list[dict]) -> dict:
    out = {}
    for method in ("score", "p_only", "valor", "recencia", "aleatorio"):
        out[method] = {k: float(np.mean([c["metodos"][method][k] for c in cuts])) for k in METRIC_KEYS}
    return out


# --- teste de atributos ----------------------------------------------------------------------------
def _size_cuts(deals: pd.DataFrame) -> tuple[float, float]:
    emp = deals.dropna(subset=["account"]).drop_duplicates("account")["employees"].to_numpy(dtype=float)
    lo, hi = np.quantile(emp, [1 / 3, 2 / 3])
    return float(lo), float(hi)


def _add_size(df: pd.DataFrame, size_cuts: tuple[float, float]) -> pd.DataFrame:
    emp = df["employees"].to_numpy(dtype=float)
    idx = np.digitize(emp, size_cuts, right=True)
    label = np.where(np.isnan(emp), None, np.array(SIZE_LABELS, dtype=object)[idx])
    return df.assign(porte=label)


ATTRIBUTES = (
    {"nome": "produto", "coluna": "product", "so_com_conta": False},
    {"nome": "região", "coluna": "regional_office", "so_com_conta": False},
    {"nome": "setor", "coluna": "sector", "so_com_conta": True},
    {"nome": "porte", "coluna": "porte", "so_com_conta": True},
)


def _attribute_cut(c: _Cut, attr: dict, size_cuts) -> dict:
    train = _add_size(c.train, size_cuts)
    pop = _add_size(c.pop, size_cuts)
    if attr["so_com_conta"]:
        train = train.loc[train["has_account"].astype(bool)]
        pop = pop.loc[pop["has_account"].astype(bool)]
    col = attr["coluna"]
    knot = c.model.knot_days
    X0_tr = age_design(train["age_days"].to_numpy(dtype=float), knot)
    X0_ev = age_design(pop["age_days"].to_numpy(dtype=float), knot)
    age_bounds = [(None, None), (None, 0.0)]
    base_fit = _fit_masked_age(X0_tr, train["y"], age_bounds)
    counts = train[col].value_counts()
    reference = sorted(counts[counts == counts.max()].index)[0]
    levels = sorted(v for v in counts.index if v != reference)

    def dummies(values):
        arr = values.to_numpy(dtype=object)
        return np.column_stack([(arr == lv).astype(float) for lv in levels])

    X_tr = np.hstack([X0_tr, dummies(train[col])])
    X_ev = np.hstack([X0_ev, dummies(pop[col])])
    fit = fit_logistic_masked(
        X_tr, train["y"], config.ATTRIBUTE_L2, penalized=range(2, X_tr.shape[1]),
        bounds=age_bounds + [(None, None)] * len(levels),
    )
    p_base = expit(X0_ev @ np.asarray(base_fit.coef))
    p_attr = expit(X_ev @ np.asarray(fit.coef))
    price = pop["sales_price"].to_numpy(dtype=float)
    gain = pop["gain"].to_numpy(dtype=float)
    yh = pop["y_h"].to_numpy(dtype=float)
    ll_base, ll_attr = log_loss(p_base, yh), log_loss(p_attr, yh)
    # diagnóstico (não decide): o mesmo log-loss dentro da amostra de treino, para mostrar se o atributo "parecia" ajudar
    y_tr = train["y"].to_numpy(dtype=float)
    tr_delta = log_loss(expit(X_tr @ np.asarray(fit.coef)), y_tr) - log_loss(expit(X0_tr @ np.asarray(base_fit.coef)), y_tr)
    rev_base, rev_attr = top_share(p_base * price, gain), top_share(p_attr * price, gain)
    return {
        "cut": c.T.strftime("%Y-%m-%d"), "n_treino": int(len(train)), "n_avaliacao": int(len(pop)),
        "log_loss_base": ll_base, "log_loss_atributo": ll_attr, "delta_log_loss": ll_attr - ll_base,
        "delta_log_loss_treino": tr_delta,
        "receita_top20_base": rev_base, "receita_top20_atributo": rev_attr, "delta_receita_top20": rev_attr - rev_base,
        "n_niveis": len(levels) + 1, "referencia": str(reference),
    }


def _fit_masked_age(X0, y, bounds) -> LogisticFit:
    return fit_logistic_masked(X0, y, 0.0, penalized=[], bounds=bounds)


def run_attribute_tests(deals: pd.DataFrame, cuts: list[_Cut]) -> list[dict]:
    """Um atributo por vez sobre a curva de idade (joelho fixo). Entra só se melhorar o log-loss em todos os cortes
    e não piorar a receita no top 20% em nenhum (regra pré-registrada)."""
    size_cuts = _size_cuts(deals)
    out = []
    for attr in ATTRIBUTES:
        per_cut = [_attribute_cut(c, attr, size_cuts) for c in cuts]
        better_ll = all(r["delta_log_loss"] < 0 for r in per_cut)
        not_worse = all(r["delta_receita_top20"] >= -_FLOAT_EPS for r in per_cut)
        out.append({
            "atributo": attr["nome"], "coluna": attr["coluna"],
            "subconjunto": "só deals com conta" if attr["so_com_conta"] else "todos os deals",
            "por_corte": per_cut,
            "melhora_log_loss_em_todos": bool(better_ll),
            "nao_piora_receita_em_nenhum": bool(not_worse),
            "entra": bool(better_ll and not_worse),
        })
    return out


# --- auditorias ---------------------------------------------------------------------------------------
def _audit(deals: pd.DataFrame, cuts: list[_Cut]) -> dict:
    """(i) modelo com o futuro (VAZADO, nunca é resultado); (ii) `has_account` sozinho."""
    ref = config.DEFAULT_REFERENCE_DATE
    leaked = fit_model(deals, ref)
    vazado, conta = [], []
    for c in cuts:
        pop = c.pop
        y, gain = pop["y"].to_numpy(dtype=int), pop["gain"].to_numpy(dtype=float)
        price = pop["sales_price"].to_numpy(dtype=float)
        age = pop["age_days"].to_numpy(dtype=float)
        honest = _mm(c.model.curve.p_win(age) * price, y, gain)
        leak = _mm(leaked.curve.p_win(age) * price, y, gain)
        vazado.append({
            "cut": c.T.strftime("%Y-%m-%d"), "rotulo": "VAZADO — modelo ajustado com dados até 31/12/2017; não é resultado",
            "knot_days": leaked.curve.knot_days, "p_fresh": leaked.curve.p_fresh, "score_vazado": leak,
            "score_honesto": honest,
            "delta_receita_top20": leak["receita_top20"] - honest["receita_top20"],
            "delta_auc": leak["auc"] - honest["auc"],
        })
        has = pop["has_account"].to_numpy(dtype=bool)
        y_f = y.astype(float)
        conta.append({
            "cut": c.T.strftime("%Y-%m-%d"), "n": int(len(pop)), "n_com_conta": int(has.sum()), "n_sem_conta": int((~has).sum()),
            "auc_has_account": auc(has.astype(float), y_f),
            "ganhos_top20_has_account": top_share(has.astype(float), y_f),
            "receita_top20_has_account": top_share(has.astype(float), gain),
            "taxa_ganho_com_conta": _mean_or_none(y_f[has]), "taxa_ganho_sem_conta": _mean_or_none(y_f[~has]),
            "ganhos_sem_conta": int(y[~has].sum()),
        })
    return {"vazado": vazado, "has_account": conta}


def _sensitivity_first_snapshot(deals: pd.DataFrame, main_cuts: list[dict]) -> dict:
    """Mesmas métricas do score com a primeira foto de treino em 28/02/2017 (sensibilidade, não alternativa)."""
    cfg = FitConfig(first_snapshot=config.SENSITIVITY_FIRST_SNAPSHOT)
    rows, as_cuts = [], []
    for main in main_cuts:
        c = _build_cut(deals, main["cut"], cfg, "plateau")
        pop = c.pop
        vecs = _vectors(c)
        y, gain = pop["y"].to_numpy(dtype=int), pop["gain"].to_numpy(dtype=float)
        mm = {m: _mm(vecs[m], y, gain) for m in ("score", "p_only")}
        rows.append({
            "cut": main["cut"], "modelo": _model_dict(c.model), "score": mm["score"], "p_only": mm["p_only"],
            "delta_receita_top20_vs_principal": mm["score"]["receita_top20"] - main["metodos"]["score"]["receita_top20"],
            "delta_auc_vs_principal": mm["score"]["auc"] - main["metodos"]["score"]["auc"],
        })
        as_cuts.append({"cut": main["cut"], "metodos": {**main["metodos"], "score": mm["score"]}})
    crit = check_criterion(as_cuts)
    return {
        "first_snapshot": config.SENSITIVITY_FIRST_SNAPSHOT, "por_corte": rows,
        "media": {k: float(np.mean([r["score"][k] for r in rows])) for k in METRIC_KEYS},
        "criterio": crit,
    }


# --- hoje -------------------------------------------------------------------------------------------------
def _hoje(deals: pd.DataFrame) -> dict:
    ref = config.DEFAULT_REFERENCE_DATE
    model = fit_model(deals, ref)
    scored = score_deals(deals, ref, model, include_prospecting=True)
    cats = {}
    for cat in config.CATEGORIES:
        part = scored.loc[scored["category"] == cat]
        cats[cat] = {
            "n": int(len(part)), "valor_tabela": float(part["sales_price"].sum()),
            "valor_esperado": None if cat == "Qualifique" else float(part["expected_value"].sum()),
        }
    eng = scored.loc[scored["category"] != "Qualifique"]
    age = eng["age_days"].to_numpy(dtype=float)
    foque = eng.loc[eng["category"] == "Foque"]
    fage = foque["age_days"].to_numpy(dtype=float)
    return {
        "as_of": ref,
        "modelo": _model_dict(model),
        "categorias": cats,
        "faixas_fixas_do_briefing": {
            "ate_90": int((age <= config.BRIEFING_FRESH_DAYS).sum()),
            "de_91_a_138": int(((age > config.BRIEFING_FRESH_DAYS) & (age <= 138)).sum()),
            "acima_de_138": int((age > 138).sum()),
        },
        "foque_por_idade": [
            {"faixa": _band_label(lo, hi), "idade_min": lo, "idade_max": hi,
             "n": int(_band_mask(fage, lo, hi).sum())}
            for lo, hi in config.FOQUE_AGE_BANDS
        ],
        "sem_conta": {cat: int((~scored.loc[scored["category"] == cat, "has_account"].astype(bool)).sum()) for cat in config.CATEGORIES},
    }


# --- orquestração ---------------------------------------------------------------------------------------
def _run_kind(deals, kind: str) -> tuple[list[_Cut], list[dict]]:
    cuts = [_build_cut(deals, T, FitConfig(), kind) for T in config.BACKTEST_CUTS]
    return cuts, [_evaluate(c) for c in cuts]


def headline_metrics(backtest: dict) -> dict:
    """O dict que `explain.how_it_works` espera (frações da média dos cortes)."""
    return dict(backtest["headline"])


def run_backtest(deals: pd.DataFrame | None = None, write: bool = True) -> dict:
    """Roda o backtest completo na ordem pré-registrada e grava `backtest_metrics.json` e `backtest_tables.md`.

    1) curva "platô + queda" nos 4 cortes; 2) critério; 3) só se falhar, o ajuste único (faixas de 15 dias + PAVA)
    e o critério de novo; 4) se ainda falhar, vale o modelo de melhor média da métrica primária (falha documentada).
    """
    from . import clean

    deals = clean.load_deals() if deals is None else deals
    cuts1, eval1 = _run_kind(deals, "plateau")
    crit1 = check_criterion(eval1)
    runs = {"plateau": {"passed": crit1["passed"], "per_cut": crit1["per_cut"], "media_receita_top20_score": _mean_metrics(eval1)["score"][PRIMARY_METRIC]}}
    final_kind, final_eval, adjusted = "plateau", eval1, False
    if not crit1["passed"]:
        adjusted = True
        _, eval2 = _run_kind(deals, "binned")
        crit2 = check_criterion(eval2)
        runs["binned"] = {"passed": crit2["passed"], "per_cut": crit2["per_cut"], "media_receita_top20_score": _mean_metrics(eval2)["score"][PRIMARY_METRIC]}
        if crit2["passed"] or runs["binned"]["media_receita_top20_score"] > runs["plateau"]["media_receita_top20_score"]:
            final_kind, final_eval = "binned", eval2
    final = check_criterion(final_eval)
    media = _mean_metrics(final_eval)
    result = {
        "config": {
            "horizon_days": config.HORIZON_DAYS, "first_snapshot": config.FIRST_SNAPSHOT,
            "reference_date": config.DEFAULT_REFERENCE_DATE, "cuts": list(config.BACKTEST_CUTS),
            "top_frac": config.TOP_FRAC, "random_seeds": config.RANDOM_SEEDS, "bootstrap_reps": config.BOOTSTRAP_REPS,
            "tie_tol": config.CRITERION_TIE_TOL, "attribute_l2": config.ATTRIBUTE_L2,
            "adjust_bin_days": config.ADJUST_BIN_DAYS, "adjust_pseudo_count": config.ADJUST_PSEUDO_COUNT,
            "methods": list(METHOD_LABELS), "method_labels": METHOD_LABELS, "primary_metric": PRIMARY_METRIC,
        },
        "criterion": {
            "rule": RULE_TEXT, "metric": PRIMARY_METRIC, "tie_tol": config.CRITERION_TIE_TOL,
            "passed": final["passed"], "adjustment_applied": adjusted, "final_curve": final_kind,
            "per_cut": final["per_cut"], "runs": runs,
        },
        "headline": {
            "n_cortes": len(final_eval), "receita_score": media["score"][PRIMARY_METRIC],
            "receita_valor": media["valor"][PRIMARY_METRIC], "receita_recencia": media["recencia"][PRIMARY_METRIC],
        },
        "cuts": final_eval,
        "media_cortes": {"metodos": media, "brier": {
            k: float(np.mean([c["brier"][k] for c in final_eval])) for k in ("modelo", "constante", "log_loss_modelo", "log_loss_constante")
        }},
        "sensibilidade_2017-02-28": _sensitivity_first_snapshot(deals, final_eval),
        "auditoria": _audit(deals, cuts1),
        "atributos": run_attribute_tests(deals, cuts1),
        "hoje": _hoje(deals),
    }
    result = _py(result)
    if write:
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.BACKTEST_JSON, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        write_tables(result)
    return result


TABLE_BLOCKS = (
    ("Critério pré-registrado, corte a corte", "scoring-criterio"),
    ("Backtest: corte × método", "scoring-backtest"),
    ("Média dos cortes", "scoring-media"),
    ("Categorias por corte", "scoring-categorias"),
    ("Calibração", "scoring-calibracao"),
    ("Bootstrap", "scoring-bootstrap"),
    ("Foque por idade", "scoring-foque-idade"),
    ("Sensibilidades", "scoring-sensibilidade"),
    ("Auditoria", "scoring-auditoria"),
    ("Atributos", "scoring-atributos"),
    ("Modelos por corte", "scoring-modelos"),
    ("Hoje", "scoring-hoje"),
)


def write_tables(result: dict, path=None) -> None:
    """Grava `backtest_tables.md` com os mesmos renderizadores dos blocos AUTO do SCORING.md."""
    from . import docs

    sources = {"facts": None, "backtest": result}
    parts = ["# Tabelas do backtest\n", "Gerado por `python -m scorer.validate`; não editar à mão.\n"]
    for title, name in TABLE_BLOCKS:
        parts.append(f"## {title}\n\n{docs.BLOCKS[name](sources).strip(chr(10))}\n")
    with open(path or config.BACKTEST_TABLES_MD, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(parts))


def main(argv=None) -> int:
    from .fmt import fmt_date, fmt_dec, fmt_pct

    sys.stdout.reconfigure(encoding="utf-8")
    result = run_backtest()
    print(f"{'corte':<12}{'método':<32}{'AUC':>7}{'ganhos top20':>14}{'receita top20':>15}")
    for cut in result["cuts"]:
        for method in ("score", "valor", "recencia", "aleatorio", "p_only"):
            m = cut["metodos"][method]
            print(
                f"{fmt_date(cut['cut']):<12}{METHOD_LABELS[method]:<32}{fmt_dec(m['auc'], 2):>7}"
                f"{fmt_pct(m['ganhos_top20'], 1):>14}{fmt_pct(m['receita_top20'], 1):>15}"
            )
    print("média dos cortes:")
    for method, m in result["media_cortes"]["metodos"].items():
        print(
            f"{'':<12}{METHOD_LABELS[method]:<32}{fmt_dec(m['auc'], 2):>7}"
            f"{fmt_pct(m['ganhos_top20'], 1):>14}{fmt_pct(m['receita_top20'], 1):>15}"
        )
    crit = result["criterion"]
    print(f"\ncurva final: {crit['final_curve']}; ajuste aplicado: {'sim' if crit['adjustment_applied'] else 'não'}")
    print("CRITÉRIO: " + ("PASSOU" if crit["passed"] else "FALHOU"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
