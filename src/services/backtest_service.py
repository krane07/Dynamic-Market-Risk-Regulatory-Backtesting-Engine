from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats


class BaselZone(str, Enum):
    GREEN = "Green"
    YELLOW = "Yellow"
    RED = "Red"


@dataclass(frozen=True)
class KupiecResult:
    statistic: float
    p_value: float
    is_rejected: bool
    expected_exceptions: float
    actual_exceptions: int
    failure_rate: float


@dataclass(frozen=True)
class ChristoffersenResult:
    stat_independence: float
    p_value_independence: bool
    is_independence_rejected: bool
    stat_conditional_coverage: float
    p_value_conditional_coverage: float
    is_cc_rejected: bool
    consecutive_breaches: int


@dataclass(frozen=True)
class RegulatoryBacktestReport:
    confidence_level: float
    total_observations: int
    basel_zone: BaselZone
    capital_multiplier: float
    kupiec: KupiecResult
    christoffersen: ChristoffersenResult
    breach_dates: list[str]


def evaluate_kupiec_pof(
    exceptions: np.ndarray, 
    confidence_level: float = 0.99, 
    significance_level: float = 0.05
) -> KupiecResult:
    """
    Computes Kupiec Proportion of Failures (POF) Likelihood Ratio test.
    """
    T = len(exceptions)
    x = int(np.sum(exceptions))
    p = 1.0 - confidence_level
    p_hat = x / T

    if x == 0:
        lr_uc = -2.0 * T * np.log(1.0 - p)
    elif x == T:
        lr_uc = -2.0 * T * np.log(p)
    else:
        # Use log likelihood ratio formulation
        term1 = x * np.log(p_hat / p)
        term2 = (T - x) * np.log((1.0 - p_hat) / (1.0 - p))
        lr_uc = 2.0 * (term1 + term2)

    lr_uc = max(0.0, float(lr_uc))
    p_value = float(stats.chi2.sf(lr_uc, df=1))

    return KupiecResult(
        statistic=lr_uc,
        p_value=p_value,
        is_rejected=p_value < significance_level,
        expected_exceptions=float(T * p),
        actual_exceptions=x,
        failure_rate=float(p_hat),
    )


def evaluate_christoffersen_independence(
    exceptions: np.ndarray,
    significance_level: float = 0.05,
    lr_uc: float = 0.0
) -> ChristoffersenResult:
    """
    Computes Christoffersen Interval Forecast Independence & Conditional Coverage tests.
    """
    T = len(exceptions)
    e = exceptions.astype(int)

    # Calculate transition states
    n00 = int(np.sum((e[:-1] == 0) & (e[1:] == 0)))
    n01 = int(np.sum((e[:-1] == 0) & (e[1:] == 1)))
    n10 = int(np.sum((e[:-1] == 1) & (e[1:] == 0)))
    n11 = int(np.sum((e[:-1] == 1) & (e[1:] == 1)))

    # Empirical transition probabilities
    pi_01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
    pi_11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
    pi = (n01 + n11) / (T - 1) if (T - 1) > 0 else 0.0

    # Helper function for safe log evaluation
    def _log_term(count: int, prob: float) -> float:
        return count * np.log(prob) if count > 0 and prob > 0 else 0.0

    # Independence log-likelihood ratio
    ll_null = _log_term(n00 + n10, 1.0 - pi) + _log_term(n01 + n11, pi)
    ll_alt = (
        _log_term(n00, 1.0 - pi_01)
        + _log_term(n01, pi_01)
        + _log_term(n10, 1.0 - pi_11)
        + _log_term(n11, pi_11)
    )

    lr_ind = max(0.0, float(-2.0 * (ll_null - ll_alt)))
    p_val_ind = float(stats.chi2.sf(lr_ind, df=1))

    # Conditional Coverage: LR_cc = LR_uc + LR_ind ~ chi2(2)
    lr_cc = lr_uc + lr_ind
    p_val_cc = float(stats.chi2.sf(lr_cc, df=2))

    return ChristoffersenResult(
        stat_independence=lr_ind,
        p_value_independence=p_val_ind,
        is_independence_rejected=p_val_ind < significance_level,
        stat_conditional_coverage=lr_cc,
        p_value_conditional_coverage=p_val_cc,
        is_cc_rejected=p_val_cc < significance_level,
        consecutive_breaches=n11,
    )


def classify_basel_zone(exceptions: int, n_obs: int = 250) -> tuple[BaselZone, float]:
    """
    Classifies the exception count into Basel Capital Accord zones.
    Default thresholds scale for standard 250-day 99% VaR.
    """
    scale = n_obs / 250.0
    green_max = int(np.floor(4 * scale))
    yellow_max = int(np.floor(9 * scale))

    if exceptions <= green_max:
        return BaselZone.GREEN, 3.00
    elif exceptions <= yellow_max:
        # Step-up penalty add-on from 3.40 up to 3.85
        step = (exceptions - green_max) / max(1, (yellow_max - green_max))
        multiplier = 3.40 + (0.45 * step)
        return BaselZone.YELLOW, round(multiplier, 2)
    else:
        return BaselZone.RED, 4.00


def run_backtest_suite(
    actual_returns: pd.Series,
    var_forecasts: pd.Series,
    confidence_level: float = 0.99
) -> RegulatoryBacktestReport:
    """
    Runs full regulatory validation suite comparing historical realized returns
    against forecasted 1-day Value at Risk (expressed as positive loss thresholds).
    """
    aligned = pd.concat([actual_returns.rename("return"), var_forecasts.rename("var")], axis=1).dropna()
    
    # An exception occurs when realized loss exceeds positive VaR: Return < -VaR
    exceptions_series = aligned["return"] < -aligned["var"]
    exceptions = exceptions_series.to_numpy(dtype=int)
    
    breach_dates = [str(d) for d in aligned.index[exceptions_series]]
    n_obs = len(exceptions)
    x = int(np.sum(exceptions))

    kupiec = evaluate_kupiec_pof(exceptions, confidence_level=confidence_level)
    christoffersen = evaluate_christoffersen_independence(exceptions, lr_uc=kupiec.statistic)
    zone, multiplier = classify_basel_zone(x, n_obs=n_obs)

    return RegulatoryBacktestReport(
        confidence_level=confidence_level,
        total_observations=n_obs,
        basel_zone=zone,
        capital_multiplier=multiplier,
        kupiec=kupiec,
        christoffersen=christoffersen,
        breach_dates=breach_dates,
    )