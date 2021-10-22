import numpy as np
import pandas as pd
import plotly.express as px
from plotly.offline import iplot
import plotly.graph_objs as go
from models.Ising import Ising

from data.data import assets, dates

class Markowitz():

    """
    Implementation of Markowitz model.
    """

    def __init__(
        self, 
        covariance : np.ndarray, 
        expected_return : np.ndarray, 
        risk_coefficient : float = 1, 
        number_of_bits : int = 1,
        date : str = dates[-1],
        assets_list : list = assets[:]
    ) -> None:
        
        # Data
        self.covariance = covariance
        self.expected_return = expected_return
        self.number_of_bits = number_of_bits
        self.risk_coefficient = risk_coefficient
        self.date = date
        self.assets_list = assets_list
        self.number_of_assets = len(assets_list)

        # Parameters to optimize
        self.portfolio = {
            'dataframe' : None,
            'array' : None,
        }

        # Conversion matrices

            ## Vector conversion

        int_to_spin_vector = np.zeros(
            (self.number_of_assets * self.number_of_bits, self.number_of_assets),
            dtype = np.float64
        )

        for a in range(self.number_of_assets):
            for b in range(self.number_of_bits):

                int_to_spin_vector[a*self.number_of_bits+b][a] = 2.0**b

            ## Matrix conversion

        int_to_spin_matrix = np.block(
            [
                [2.0**b * np.eye(self.number_of_assets)] 
                for b in range(self.number_of_bits)
            ]
        )

        self.conversion_matrix = {
            'vector': int_to_spin_vector,
            'matrix': int_to_spin_matrix,
        }         

    def __repr__(self) -> str:
        
        message = f"Markowitz portfolio: {self.number_of_assets} {self.number_of_bits}-bits encoded S&P500 assets (updated {self.date}) with risk aversion of {self.risk_coefficient}: {self.assets_list}."

        if self.portfolio is not None:

            message += f"\nOptimal portfolio:\n{self.portfolio['dataframe']}"    

        return message    

    @classmethod
    def from_csv(
        cls,
        risk_coefficient : float = 1, 
        number_of_bits : int = 1,
        date : str = dates[-1],
        assets_list : list = assets[:]
    ) -> None:

        """
        Retrieves the data for the Markowitz model from .csv files.
        """
        
        covariance_filename = "./data/cov.csv"
        expected_return_filename = "./data/mu.csv"

        complete_monthly_returns = pd.read_csv(expected_return_filename)
        complete_monthly_returns.set_index('Date', inplace = True)

        cov = pd.read_csv(covariance_filename)
        cov.set_index('Unnamed: 0', inplace = True)

        mu = np.expand_dims(complete_monthly_returns[assets_list].loc[date].to_numpy(),1)
        sigma = cov[assets_list].loc[assets_list].to_numpy()

        covariance = sigma
        expected_return = mu

        return Markowitz(
            covariance,
            expected_return,
            risk_coefficient = risk_coefficient,
            number_of_bits = number_of_bits,
            date = date,
            assets_list = assets_list
        )    

    def to_Ising(self) -> Ising:

        """
        Generates the equivalent Ising model.
        """

        sigma = self.conversion_matrix['matrix'] @ self.covariance @ self.conversion_matrix['matrix'].T
        mu = self.conversion_matrix['vector'] @ self.expected_return

        J = -self.risk_coefficient/2 * sigma
        h = self.risk_coefficient/2 * sigma @ np.ones((self.number_of_assets * self.number_of_bits, 1)) - mu 
        
        return Ising(J, h)

    def optimize(
        self,
        kerr_constant : float = 1,
        detuning_frequency : float = 1,
        pressure = lambda t : 0.01 * t,
        time_step : float = 0.01,
        simulation_time : int = 600,
        symplectic_parameter : int = 2,
        window_size = 50,
        stop_criterion = True,
        check_frequency : int = 1000,
    ) -> None:

        """
        Computes the optimal portfolio for this Markowitz model.
        """

        ising = self.to_Ising()  
        ising.optimize(
            kerr_constant = kerr_constant,
            detuning_frequency = detuning_frequency,
            pressure = pressure,
            time_step = time_step,
            symplectic_parameter = symplectic_parameter,
            simulation_time = simulation_time,
            window_size = window_size,
            stop_criterion = stop_criterion,
            check_frequency = check_frequency
        )
        print(ising.energy)
        self.portfolio['array'] = (self.conversion_matrix['vector']).T @ ((ising.ground_state + 1)/2)
        optimized_portfolio = self.portfolio['array'].T[0]

        assets_to_purchase = [self.assets_list[ind] for ind in range(len(self.assets_list)) if optimized_portfolio[ind] > 0]
        stocks_to_purchase = [optimized_portfolio[ind] for ind in range(len(optimized_portfolio)) if optimized_portfolio[ind] > 0]
        total_stocks = sum(stocks_to_purchase)

        self.portfolio['dataframe'] = pd.DataFrame(
            {
                'assets': assets_to_purchase,
                'stocks': stocks_to_purchase,
                'ratios': [round(100 * stock/total_stocks, 3) for stock in stocks_to_purchase]
            }
        ).sort_values(by=['assets'])

    ############################
    # Graphical representation #
    ############################

    def pie(self) -> None:

        if self.portfolio['dataframe'] is not None:

            fig = px.pie(
                self.portfolio['dataframe'],
                values = 'stocks',
                names = 'assets',
                title = 'Optimal portfolio'
            )
            fig.show()

    def table(self) -> None:

        if self.portfolio['dataframe'] is not None:

            trace = go.Table(
            header = dict(
                values = [
                    "Assets",
                    "Stocks to purchase",
                    'Percentage of capital invested'
                ],
                fill = dict(color='#C2D4FF'),
                align = ['left'] * 5
            ),
            cells = dict(
                values = [
                    self.portfolio['dataframe'].assets,
                    self.portfolio['dataframe'].stocks,
                    self.portfolio['dataframe'].ratios
                ],
                fill = dict(color='#F5F8FF'),
                align = ['left'] * 5)
            )

            data = [trace]
            iplot(data, filename = 'pandas_table')  