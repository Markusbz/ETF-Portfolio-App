import scipy.optimize as opt
import numpy as np
import pandas as pd
from .backtester import PortfolioBacktester

class PortfolioOptimizer:
    def __init__(self, backtester: PortfolioBacktester):
        self.backtester = backtester

    def sharpe_objective_function(self, x0: np.array):
        x0 = pd.Series(x0, index=self.backtester.portfolio_weights.index)
        self.backtester.portfolio_weights = x0
        returns = self.backtester.calculate_portfolio_return_timeseries()

        return -self.backtester.calculate_period_stats(returns)['sharpe']

    def optimize_portfolio(self, bounds: list, constraints: list):
        initial_weights = self.backtester.portfolio_weights.to_numpy()
        result = opt.minimize(
            self.sharpe_objective_function,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        if result.success:
            optimized_weights = pd.Series(result.x, index=self.backtester.portfolio_weights.index)
            self.backtester.portfolio_weights = optimized_weights
            return optimized_weights
        else:
            raise ValueError("Optimization failed: " + result.message)