from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats

from src.services.dcc_garch_service import DCCGARCHEngine

@dataclass(frozen=True)
class RiskMetricsResult:
    confidence_level: float
    horizon_days: int
    current_portfolio_value: float
    
    # Historical Simulation
    var_historical_pct: float
    var_historical_currency: float
    es_historical_pct: float
    es_historical_currency: float
    
    # Parametric Normal
    var_parametric_pct: float
    var_parametric_currency: float
    es_parametric_pct: float
    es_parametric_currency: float
    
    # Parametric Student's t
    var_t_pct: float
    var_t_currency: float
    es_t_pct: float
    es_t_currency: float
    t_degrees_of_freedom: float


def compute_portfolio_risk_metrics(
    returns_df: pd.DataFrame,
    portfolio_returns: pd.Series,
    latest_weights: pd.Series,
    current_value: float,
    confidence_level: float = 0.99,
    horizon_days: int = 1
) -> RiskMetricsResult:
    """
    Computes 1-day Value at Risk (VaR) and Expected Shortfall (ES)
    across Historical Simulation, Parametric Normal, and Student's t models.

    Args:
        returns_df: T x N individual asset log returns.
        portfolio_returns: T x 1 daily portfolio log returns.
        latest_weights: Current weight allocated to each asset (aligned to returns_df columns).
        current_value: Current monetary valuation of the portfolio.
        confidence_level: Risk confidence percentile (typically 0.95 or 0.99).
        horizon_days: Risk forecasting horizon (default 1-day).

    Returns:
        RiskMetricsResult containing percentage and currency risk values.
    """
    if not (0.5 < confidence_level < 1.0):
        raise ValueError("Confidence level must be strictly between 0.50 and 1.00.")

    ret_series = portfolio_returns.to_numpy()
    tail_prob = 1.0 - confidence_level

    # -------------------------------------------------------------
    # 1. Historical Simulation
    # -------------------------------------------------------------
    hist_quantile = np.percentile(ret_series, tail_prob * 100)
    var_hist_pct = float(-hist_quantile)

    tail_losses = ret_series[ret_series <= hist_quantile]
    es_hist_pct = float(-np.mean(tail_losses)) if len(tail_losses) > 0 else var_hist_pct

    # -------------------------------------------------------------
    # 2. Parametric Normal (Variance-Covariance)
    # -------------------------------------------------------------
    w = latest_weights.reindex(returns_df.columns).to_numpy()
    cov_matrix = returns_df.cov().to_numpy()

    # Annualized or daily portfolio variance: sigma_p^2 = w^T * Sigma * w
    port_variance = np.dot(w.T, np.dot(cov_matrix, w))
    port_sigma = np.sqrt(max(port_variance, 1e-12))
    port_mean = float(np.mean(ret_series))

    # Normal critical value
    z_alpha = stats.norm.ppf(confidence_level)
    phi_z = stats.norm.pdf(z_alpha)

    var_param_pct = float(z_alpha * port_sigma - port_mean)
    es_param_pct = float(port_sigma * (phi_z / tail_prob) - port_mean)

    # -------------------------------------------------------------
    # 3. Parametric Student's t (Fat-Tailed)
    # -------------------------------------------------------------
    # Fit degrees of freedom (df), loc, scale to portfolio returns
    t_params = stats.t.fit(ret_series)
    df_fit, loc_fit, scale_fit = t_params

    # Bound degrees of freedom for stability (nu > 2 ensures finite variance)
    df_fit = max(df_fit, 2.01)

    t_critical = stats.t.ppf(tail_prob, df=df_fit)
    var_t_pct = float(-(loc_fit + scale_fit * t_critical))

    # Analytical Expected Shortfall for Student's t
    t_pdf_val = stats.t.pdf(t_critical, df=df_fit)
    es_term = (t_pdf_val / tail_prob) * ((df_fit + t_critical**2) / (df_fit - 1.0))
    es_t_pct = float(-(loc_fit - scale_fit * es_term))

    # -------------------------------------------------------------
    # Scale across time horizon if horizon_days > 1 (Square-root rule)
    # -------------------------------------------------------------
    sqrt_h = np.sqrt(horizon_days)
    var_hist_pct *= sqrt_h
    es_hist_pct *= sqrt_h
    var_param_pct *= sqrt_h
    es_param_pct *= sqrt_h
    var_t_pct *= sqrt_h
    es_t_pct *= sqrt_h

    return RiskMetricsResult(
        confidence_level=confidence_level,
        horizon_days=horizon_days,
        current_portfolio_value=current_value,
        
        var_historical_pct=var_hist_pct,
        var_historical_currency=var_hist_pct * current_value,
        es_historical_pct=es_hist_pct,
        es_historical_currency=es_hist_pct * current_value,
        
        var_parametric_pct=var_param_pct,
        var_parametric_currency=var_param_pct * current_value,
        es_parametric_pct=es_param_pct,
        es_parametric_currency=es_param_pct * current_value,
        
        var_t_pct=var_t_pct,
        var_t_currency=var_t_pct * current_value,
        es_t_pct=es_t_pct,
        es_t_currency=es_t_pct * current_value,
        t_degrees_of_freedom=float(df_fit)
    )

def compute_dcc_garch_risk_metrics(
    returns_df: pd.DataFrame,
    latest_weights: pd.Series,
    current_value: float,
    confidence_level: float = 0.99,
    horizon_days: int = 1
) -> dict:
    """
    Computes 1-step-ahead dynamic VaR and Expected Shortfall using DCC-GARCH(1,1).
    """
    # 1. Fit DCC-GARCH and extract forecasted covariance Sigma_{t+1}
    engine = DCCGARCHEngine(returns_df)
    forecast = engine.forecast_covariance()
    
    # 2. Align weights to columns
    w = latest_weights.reindex(forecast.tickers).to_numpy()
    
    # 3. Dynamic 1-step portfolio volatility forecast: sigma_{p, t+1} = sqrt(w^T * Sigma_{t+1} * w)
    dynamic_port_variance = float(np.dot(w.T, np.dot(forecast.forecasted_covariance, w)))
    dynamic_port_sigma = np.sqrt(max(dynamic_port_variance, 1e-12))
    
    # Square-root of time scaling
    sqrt_h = np.sqrt(horizon_days)
    dynamic_port_sigma *= sqrt_h
    
    # 4. Critical quantiles
    z_alpha = stats.norm.ppf(confidence_level)
    phi_z = stats.norm.pdf(z_alpha)
    tail_prob = 1.0 - confidence_level
    
    var_dcc_pct = float(z_alpha * dynamic_port_sigma)
    es_dcc_pct = float(dynamic_port_sigma * (phi_z / tail_prob))
    
    return {
        "var_dcc_pct": var_dcc_pct,
        "var_dcc_currency": var_dcc_pct * current_value,
        "es_dcc_pct": es_dcc_pct,
        "es_dcc_currency": es_dcc_pct * current_value,
        "dynamic_daily_sigma": dynamic_port_sigma / sqrt_h,
        "dcc_alpha": forecast.dcc_alpha,
        "dcc_beta": forecast.dcc_beta,
        "forecasted_correlation": forecast.forecasted_correlation
    }