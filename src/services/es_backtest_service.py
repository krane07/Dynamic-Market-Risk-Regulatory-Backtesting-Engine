from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class AcerbiSzekelyResult:
    test_statistic_z1: float
    test_statistic_z2: float
    p_value_z1: float
    p_value_z2: float
    is_z1_rejected: bool
    is_z2_rejected: bool
    total_breaches: int
    confidence_level: float
    simulations: int


def evaluate_acerbi_szekely(
    realized_returns: pd.Series,
    var_forecasts: pd.Series,
    es_forecasts: pd.Series,
    confidence_level: float = 0.975,
    num_simulations: int = 2500,
    significance_level: float = 0.05,
    dist: str = "normal",
    df_t: float = 5.0
) -> AcerbiSzekelyResult:
    """
    Computes Acerbi-Szekely (2014) Z1 and Z2 test statistics for Expected Shortfall
    and determines empirical p-values via parametric Monte Carlo under H0.

    Args:
        realized_returns: T daily observed portfolio log returns.
        var_forecasts: T 1-day VaR forecasts (positive losses).
        es_forecasts: T 1-day Expected Shortfall forecasts (positive losses).
        confidence_level: Alpha coverage level (FRTB standard is 0.975).
        num_simulations: Monte Carlo replications under H0 to derive null distribution.
        significance_level: Test rejection cutoff (default 0.05).
        dist: Distribution assumed by model ('normal' or 't').
        df_t: Degrees of freedom if dist='t'.
    """
    aligned = pd.concat([
        realized_returns.rename("ret"),
        var_forecasts.rename("var"),
        es_forecasts.rename("es")
    ], axis=1).dropna()

    T = len(aligned)
    p = 1.0 - confidence_level
    
    losses = -aligned["ret"].to_numpy()
    var_vals = aligned["var"].to_numpy()
    es_vals = aligned["es"].to_numpy()

    # Breach indicator: loss exceeds VaR
    indicators = (losses > var_vals).astype(float)
    total_breaches = int(np.sum(indicators))

    # Observed Z1 statistic: sum(L * I) / (T * p * ES) - 1
    numerator_z1 = np.sum((losses * indicators) / es_vals)
    z1_obs = float((numerator_z1 / (T * p)) - 1.0)

    # Observed Z2 statistic: (1 / N) * sum(L * I / ES) - 1
    if total_breaches > 0:
        z2_obs = float((numerator_z1 / total_breaches) - 1.0)
    else:
        z2_obs = 0.0

    # -------------------------------------------------------------
    # Monte Carlo simulation under H0 to compute exact p-values
    # -------------------------------------------------------------
    rng = np.random.default_rng(seed=42)

    # Convert positive VaR back to loss quantiles under standardized distribution
    if dist == "t":
        # Standardized t-distribution scale
        sim_losses = -rng.standard_t(df=df_t, size=(num_simulations, T)) * np.sqrt((df_t - 2.0) / df_t)
        # Normalized standard ES and VaR
        t_crit = stats.t.ppf(confidence_level, df=df_t)
        t_scale = np.sqrt((df_t - 2.0) / df_t)
        var_std = t_crit * t_scale
        # Theoretical ES for standardized t
        es_std = (stats.t.pdf(t_crit, df=df_t) / p) * ((df_t + t_crit**2) / (df_t - 1.0)) * t_scale
    else:
        # Standard normal
        sim_losses = -rng.standard_normal(size=(num_simulations, T))
        var_std = stats.norm.ppf(confidence_level)
        es_std = stats.norm.pdf(var_std) / p

    # Indicators for simulated paths
    sim_indicators = (sim_losses > var_std).astype(float)
    sim_breach_counts = np.sum(sim_indicators, axis=1)

    # Compute simulated Z1 distribution: shape (num_simulations,)
    sim_numerators = np.sum(sim_losses * sim_indicators, axis=1) / es_std
    z1_sim = (sim_numerators / (T * p)) - 1.0

    # Compute simulated Z2 distribution
    z2_sim = np.zeros(num_simulations)
    valid_breaches = sim_breach_counts > 0
    z2_sim[valid_breaches] = (sim_numerators[valid_breaches] / sim_breach_counts[valid_breaches]) - 1.0

    # One-sided empirical p-values (testing if observed risk is worse than H0)
    p_val_z1 = float(np.mean(z1_sim >= z1_obs))
    p_val_z2 = float(np.mean(z2_sim >= z2_obs))

    return AcerbiSzekelyResult(
        test_statistic_z1=z1_obs,
        test_statistic_z2=z2_obs,
        p_value_z1=p_val_z1,
        p_value_z2=p_val_z2,
        is_z1_rejected=p_val_z1 < significance_level,
        is_z2_rejected=p_val_z2 < significance_level,
        total_breaches=total_breaches,
        confidence_level=confidence_level,
        simulations=num_simulations
    )