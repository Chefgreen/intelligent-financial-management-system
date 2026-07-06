"""budget_engine.py — 50/30/20 rule budget recommendations"""

NEEDS = frozenset({"rent","groceries","utilities","transport","healthcare","insurance","food"})

class BudgetRecommendationEngine:
    def recommended_budget(self, income):
        return round(income * 0.90, 2) if income and income > 0 else 0.0

    def budget_status(self, expense, income):
        if not income or income <= 0: return "UNKNOWN"
        r = expense / income
        if r <= 0.80: return "ON_TRACK"
        if r <= 1.00: return "AT_RISK"
        return "OVER_BUDGET"

    def category_budgets(self, income, hist):
        if not income or income <= 0 or not hist: return {}
        np_ = round(income * 0.50, 2); wp = round(income * 0.30, 2)
        tn = sum(v for k,v in hist.items() if k.lower() in NEEDS)
        tw = sum(v for k,v in hist.items() if k.lower() not in NEEDS)
        out = {}
        for cat, spend in hist.items():
            is_need = cat.lower() in NEEDS
            pool = np_ if is_need else wp
            total = tn if is_need else tw
            out[cat] = round(pool * spend / total, 2) if total > 0 else 0.0
        return out

    def projected_savings(self, income, expense):
        return round(income - expense, 2)

    def target_savings(self, income):
        return round(income * 0.20, 2)