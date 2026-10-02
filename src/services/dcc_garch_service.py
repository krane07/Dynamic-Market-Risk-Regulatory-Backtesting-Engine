from dataclasses import dataclass
import numpy as np
import pandas as pd
from arch import arch_model
from scipy.optimize import minimize


@dataclass(frozen=True)
class DCCForecastResult:
    forecasted_covariance: np.ndarray      # N x N covariance matrix for t+1
    forecasted_correlation: np.ndarray     # N x N correlation matrix for t+1
    forecasted_volatilities: np.ndarray    # N vector of 1-step-ahead std devs
    dcc_alpha: float                       # DCC parameter a
    dcc_beta: float                        # DCC parameter b
    tickers: list[str]


class DCCGARCHEngine:
    def __init__(self, returns_df: pd.DataFrame):
        """
        Initializes the DCC-GARCH(1,1) engine.
        
        Args:
            returns_df: T x N dataframe of aligned daily asset log returns.
        """
        self.returns_df = returns_df
        self.tickers = list(returns_df.columns)
        self.T, self.N = returns_df.shape

    def fit_univariate_garch(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Step 1: Fit individual GARCH(1,1) to each asset series.
        
        Returns:
            - std_residuals: T x N matrix of epsilon_t
            - conditional_vols: T x N matrix of conditional standard deviations
            - next_day_vols: N vector of sigma_{i, t+1} forecasts
        """
        std_residuals = np.zeros((self.T, self.N))
        conditional_vols = np.zeros((self.T, self.N))
        next_day_vols = np.zeros(self.N)

        for i, col in enumerate(self.tickers):
            # Rescale returns to percentage points for numerical optimizer stability
            series = self.returns_df[col] * 100.0
            
            # GARCH(1,1) with Constant Mean
            am = arch_model(series, mean="Constant", vol="GARCH", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)

            # Extract conditional volatility: sigma_t
            h_t = res.conditional_volatility / 100.0
            conditional_vols[:, i] = h_t

            # Standardized residuals: epsilon_t = (r_t - mu) / sigma_t
            resid = (series - res.params["mu"]) / 100.0
            std_residuals[:, i] = resid / h_t

            # 1-day forward volatility forecast: sqrt(h_{t+1})
            forecast = res.forecast(horizon=1)
            next_day_var = forecast.variance.iloc[-1, 0] / (100.0 ** 2)
            next_day_vols[i] = np.sqrt(next_day_var)

        return std_residuals, conditional_vols, next_day_vols

    def _dcc_log_likelihood(self, params: np.ndarray, eps: np.ndarray, Q_bar: np.ndarray) -> float:
        """
        Negative quasi-log-likelihood for the DCC second-stage optimization.
        """
        a, b = params
        if a < 0 or b < 0 or (a + b) >= 0.9999:
            return 1e10

        T, N = eps.shape
        Q_t = Q_bar.copy()
        log_lik = 0.0

        for t in range(T):
            e_prev = eps[t - 1 : t, :].T  # N x 1 vector
            Q_t = (1 - a - b) * Q_bar + a * np.dot(e_prev, e_prev.T) + b * Q_t

            # Rescale Q_t to get correlation matrix R_t
            inv_diag = 1.0 / np.sqrt(np.maximum(np.diag(Q_t), 1e-8))
            R_t = Q_t * np.outer(inv_diag, inv_diag)

            # Ensure positive definiteness
            try:
                sign, logdet = np.linalg.slogdet(R_t)
                if sign <= 0:
                    return 1e10
                inv_R_t = np.linalg.inv(R_t)
            except np.linalg.LinAlgError:
                return 1e10

            e_t = eps[t : t + 1, :].T
            # DCC log-likelihood component: 0.5 * (log|R_t| + e_t' * R_t^-1 * e_t - e_t' * e_t)
            log_lik += 0.5 * (logdet + np.dot(e_t.T, np.dot(inv_R_t, e_t))[0, 0] - np.dot(e_t.T, e_t)[0, 0])

        return float(log_lik)

    def forecast_covariance(self) -> DCCForecastResult:
        """
        Executes Steps 1, 2, and 3 to yield the 1-step-ahead conditional covariance matrix.
        """
        # Step 1: Univariate GARCH fits
        std_residuals, _, next_day_vols = self.fit_univariate_garch()

        # Step 2: Unconditional correlation of standardized residuals
        Q_bar = np.cov(std_residuals, rowvar=False)

        # Optimize DCC parameters (a, b)
        init_guess = np.array([0.03, 0.92])
        bounds = ((1e-5, 0.2), (0.7, 0.999))
        constraints = {"type": "ineq", "fun": lambda p: 0.9999 - (p[0] + p[1])}

        opt_res = minimize(
            fun=self._dcc_log_likelihood,
            x0=init_guess,
            args=(std_residuals, Q_bar),
            bounds=bounds,
            constraints=constraints,
            method="SLSQP",
            options={"maxiter": 100, "ftol": 1e-5}
        )

        a_opt, b_opt = opt_res.x if opt_res.success else (0.03, 0.93)

        # Step 3: Run the recursion forward to step T+1
        Q_t = Q_bar.copy()
        for t in range(self.T):
            e_t = std_residuals[t : t + 1, :].T
            Q_t = (1 - a_opt - b_opt) * Q_bar + a_opt * np.dot(e_t, e_t.T) + b_opt * Q_t

        # 1-step-ahead forecasted correlation matrix R_{t+1}
        inv_diag = 1.0 / np.sqrt(np.maximum(np.diag(Q_t), 1e-8))
        R_next = Q_t * np.outer(inv_diag, inv_diag)

        # 1-step-ahead forecasted covariance matrix: Sigma_{t+1} = D_{t+1} * R_{t+1} * D_{t+1}
        D_next = np.diag(next_day_vols)
        Sigma_next = np.dot(D_next, np.dot(R_next, D_next))

        return DCCForecastResult(
            forecasted_covariance=Sigma_next,
            forecasted_correlation=R_next,
            forecasted_volatilities=next_day_vols,
            dcc_alpha=float(a_opt),
            dcc_beta=float(b_opt),
            tickers=self.tickers
        )