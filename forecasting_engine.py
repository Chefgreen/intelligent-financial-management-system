"""forecasting_engine.py — OLS linear regression + weighted rolling average"""

class ForecastingEngine:
    def forecast(self, data):
        if not data: return 0.0
        return self.rolling_average(data) if len(data) < 3 else self.linear_regression_forecast(data)

    def method_name(self, n):
        return "AVERAGE" if n < 3 else "LINEAR_REGRESSION"

    def rolling_average(self, data):
        if not data: return 0.0
        ws = tw = 0.0
        for i, v in enumerate(data):
            w = i + 1; ws += v * w; tw += w
        return round(ws / tw, 2)

    def linear_regression_forecast(self, data):
        n = len(data)
        if n < 2: return self.rolling_average(data)
        x = list(range(1, n+1)); y = list(data)
        sx=sum(x); sy=sum(y); sxy=sum(a*b for a,b in zip(x,y)); sx2=sum(a*a for a in x)
        d = n*sx2 - sx*sx
        if d == 0: return self.rolling_average(data)
        b = (n*sxy - sx*sy)/d; a = (sy - b*sx)/n
        return round(max(a + b*(n+1), 0.0), 2)

    def get_trend_slope(self, data):
        n = len(data)
        if n < 2: return 0.0
        x = list(range(1,n+1)); y = list(data)
        sx=sum(x); sy=sum(y); sxy=sum(a*b for a,b in zip(x,y)); sx2=sum(a*a for a in x)
        d = n*sx2 - sx*sx
        return 0.0 if d == 0 else (n*sxy - sx*sy)/d