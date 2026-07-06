"""prediction.py — Module 5: AI Expense Prediction"""

from collections import defaultdict
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, session
from functools import wraps
from forecasting_engine import ForecastingEngine
from budget_engine import BudgetRecommendationEngine

prediction_bp = Blueprint("prediction", __name__)
_mysql = None
_fe = ForecastingEngine()
_be = BudgetRecommendationEngine()

def init_prediction(m):
    global _mysql
    _mysql = m

def _auth(f):
    @wraps(f)
    def w(*a, **k):
        if "user_id" not in session:
            return jsonify({"error":"Not authenticated"}), 401
        return f(*a, **k)
    return w

@prediction_bp.route("/api/prediction")
@_auth
def api_prediction():
    return jsonify(_predict(session["user_id"]))

def _predict(uid):
    if not _mysql:
        return {"error": "Not initialised"}
    end = datetime.now(); start = end - timedelta(days=186)
    rows = _fetch(uid, start, end)
    if not rows:
        return {"predicted_monthly_expense":0.0,"predicted_monthly_income":0.0,
                "recommended_monthly_budget":0.0,"projected_savings":0.0,
                "budget_status":"NO_DATA","category_budgets":{},"category_forecasts":{},
                "forecast_method":"INSUFFICIENT_DATA","months_analysed":0,
                "message":"Add transactions to generate predictions."}
    monthly = defaultdict(lambda:{"income":0.0,"expense":0.0})
    cats    = defaultdict(lambda: defaultdict(float))
    for r in rows:
        k = r["date"][:7]; amt = float(r["amount"])
        if r["type"] in ("income","expense"):
            monthly[k][r["type"]] += amt
        if r["type"] == "expense":
            cats[r["category"]][k] += amt
    sm = sorted(monthly.keys())
    pe = _fe.forecast([monthly[m]["expense"] for m in sm])
    pi = _fe.forecast([monthly[m]["income"]  for m in sm])
    cat_avg  = {c: round(sum(v.values())/6,2) for c,v in cats.items()}
    cat_fore = {c: _fe.forecast([v.get(m,0) for m in sm]) for c,v in cats.items()}
    return {"predicted_monthly_expense":pe,"predicted_monthly_income":pi,
            "recommended_monthly_budget":_be.recommended_budget(pi),
            "projected_savings":_be.projected_savings(pi,pe),
            "budget_status":_be.budget_status(pe,pi),
            "category_budgets":_be.category_budgets(pi,cat_avg),
            "category_forecasts":cat_fore,
            "forecast_method":_fe.method_name(len(sm)),
            "months_analysed":len(sm)}

def _fetch(uid, start, end):
    try:
        cur = _mysql.connection.cursor()
        cur.execute("""SELECT type, category, CAST(amount AS CHAR) AS amount,
                              DATE_FORMAT(date,'%%Y-%%m-%%d') AS date
                       FROM transactions WHERE user_id=%s AND date BETWEEN %s AND %s
                       ORDER BY date""", (uid, start.date(), end.date()))
        rows = cur.fetchall(); cur.close()
        if rows and not isinstance(rows[0], dict):
            rows = [dict(zip(["type","category","amount","date"],r)) for r in rows]
        return list(rows)
    except Exception as e:
        print(f"[PREDICTION] {e}"); return []