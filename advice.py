"""
advice.py — Module 6: Financial Advice & Recommendations
==========================================================
Analyses a user's transactions and generates personalised,
explained recommendations in plain English.

Advice categories:
  - Overspending alerts (actual vs 50/30/20 ideal)
  - Savings rate health
  - Category-specific tips
  - Goal progress warnings
  - Spending trend alerts
"""

from __future__ import annotations
from flask import Blueprint, jsonify, session
from auth import api_login_required
from analysis import _fetch, get_savings_summary, get_category_summary
from datetime import datetime, timedelta

advice_bp = Blueprint("advice", __name__)
_mysql = None

def init_advice(mysql_instance):
    global _mysql
    _mysql = mysql_instance

NEEDS_CATS = {"rent","groceries","utilities","transport","healthcare","insurance","food"}
WANTS_CATS = {"entertainment","dining","shopping","subscriptions","education","other"}


@advice_bp.route("/api/advice")
@api_login_required
def api_advice():
    """
    GET /api/advice
    Returns a list of personalised financial advice items, each with:
      - type:     'warning' | 'tip' | 'success' | 'goal'
      - title:    short headline
      - message:  plain-English explanation
      - action:   suggested next step
    """
    items = generate_advice(session["user_id"])
    return jsonify({"advice": items, "count": len(items)})


def generate_advice(user_id: int) -> list:
    """Core advice generation — returns list of advice dicts."""
    advice = []

    # ── Fetch data ──────────────────────────────────────────────────
    rows = _fetch()
    if not rows:
        return [{
            "type":    "tip",
            "title":   "Start tracking your finances",
            "message": "Add your first income and expense transactions. The more data you add, the more personalised your advice becomes.",
            "action":  "Go to Add Transaction",
            "action_url": "/transactions/add"
        }]

    summary = get_savings_summary()
    cat_sum = get_category_summary()

    total_income   = summary["total_income"]
    total_expenses = summary["total_expenses"]
    net_savings    = summary["net_savings"]
    savings_rate   = summary["savings_rate"]

    # ── 1. Savings rate advice ──────────────────────────────────────
    if total_income > 0:
        if savings_rate >= 20:
            advice.append({
                "type":    "success",
                "title":   f"Great savings rate — {savings_rate}%",
                "message": f"You are saving {savings_rate}% of your income. Financial experts recommend saving at least 20%. You are on track.",
                "action":  "Keep it up — consider setting a savings goal",
                "action_url": "/profile/goals"
            })
        elif savings_rate >= 10:
            advice.append({
                "type":    "warning",
                "title":   f"Savings rate below target — {savings_rate}%",
                "message": f"You are saving {savings_rate}% of your income, but the recommended target is 20%. Try reducing your top spending categories to increase this.",
                "action":  "Review your top expenses",
                "action_url": "/transactions/"
            })
        elif savings_rate > 0:
            advice.append({
                "type":    "warning",
                "title":   f"Low savings rate — only {savings_rate}%",
                "message": f"You are saving just {savings_rate}% of your income. At this rate it will take much longer to reach any financial goals. Aim to cut expenses in the Wants category.",
                "action":  "See spending breakdown",
                "action_url": "/dashboard"
            })
        else:
            advice.append({
                "type":    "warning",
                "title":   "You are spending more than you earn",
                "message": f"Your total expenses (K {total_expenses:,.2f}) exceed your income (K {total_income:,.2f}). This is unsustainable — review your largest expense categories immediately.",
                "action":  "Review all transactions",
                "action_url": "/transactions/"
            })

    # ── 2. Per-category overspending vs 50/30/20 ───────────────────
    if total_income > 0 and cat_sum["labels"]:
        needs_budget = total_income * 0.50
        wants_budget = total_income * 0.30

        needs_actual = sum(
            amt for cat, amt in zip(cat_sum["labels"], cat_sum["amounts"])
            if cat.lower() in NEEDS_CATS
        )
        wants_actual = sum(
            amt for cat, amt in zip(cat_sum["labels"], cat_sum["amounts"])
            if cat.lower() in WANTS_CATS
        )

        if needs_actual > needs_budget * 1.1:
            over = needs_actual - needs_budget
            advice.append({
                "type":    "warning",
                "title":   "Essential expenses are over the 50% limit",
                "message": f"Your Needs spending (K {needs_actual:,.2f}) exceeds the recommended 50% limit (K {needs_budget:,.2f}) by K {over:,.2f}. Consider if any 'needs' can be reduced — e.g. cheaper utilities, shopping around for insurance.",
                "action":  "See category breakdown",
                "action_url": "/dashboard"
            })

        if wants_actual > wants_budget * 1.1:
            over = wants_actual - wants_budget
            advice.append({
                "type":    "warning",
                "title":   "Lifestyle spending is over the 30% limit",
                "message": f"Your Wants spending (K {wants_actual:,.2f}) exceeds the recommended 30% limit (K {wants_budget:,.2f}) by K {over:,.2f}. Entertainment, dining, and shopping are common culprits. Try the 48-hour rule before non-essential purchases.",
                "action":  "Review transactions",
                "action_url": "/transactions/"
            })

    # ── 3. Single largest expense category ─────────────────────────
    if cat_sum["labels"]:
        top_cat    = cat_sum["labels"][0]
        top_amount = cat_sum["amounts"][0]
        top_pct    = round(top_amount / total_expenses * 100, 1) if total_expenses > 0 else 0

        if top_pct > 40:
            advice.append({
                "type":    "warning",
                "title":   f"{top_cat} accounts for {top_pct}% of spending",
                "message": f"A single category ({top_cat}: K {top_amount:,.2f}) makes up {top_pct}% of all your expenses. High concentration in one category is a risk. Diversify or find ways to reduce this specific cost.",
                "action":  "View transactions",
                "action_url": "/transactions/"
            })

    # ── 4. Recent spending spike ────────────────────────────────────
    this_month = datetime.now().strftime("%Y-%m")
    last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    this_total = sum(float(r["amount"]) for r in rows if r["type"]=="expense" and r["date"][:7]==this_month)
    last_total = sum(float(r["amount"]) for r in rows if r["type"]=="expense" and r["date"][:7]==last_month)

    if last_total > 0 and this_total > last_total * 1.25:
        spike_pct = round((this_total - last_total) / last_total * 100, 0)
        advice.append({
            "type":    "warning",
            "title":   f"Spending spike — up {spike_pct:.0f}% vs last month",
            "message": f"Your spending this month (K {this_total:,.2f}) is {spike_pct:.0f}% higher than last month (K {last_total:,.2f}). Check if this is a one-off or a new pattern that needs addressing.",
            "action":  "Check recent transactions",
            "action_url": "/transactions/"
        })
    elif last_total > 0 and this_total < last_total * 0.8:
        save_pct = round((last_total - this_total) / last_total * 100, 0)
        advice.append({
            "type":    "success",
            "title":   f"Spending down {save_pct:.0f}% vs last month",
            "message": f"You spent K {this_total:,.2f} this month vs K {last_total:,.2f} last month — a {save_pct:.0f}% reduction. Well done! Consider putting the difference directly into savings.",
            "action":  "Set a savings goal",
            "action_url": "/profile/goals"
        })

    # ── 5. Goals check from DB ──────────────────────────────────────
    if _mysql:
        try:
            cur = _mysql.connection.cursor()
            cur.execute("""
                SELECT
                    goal_name                                    AS name,
                    target_amount                                AS target,
                    saved_amount                                 AS saved,
                    deadline,
                    ROUND(saved_amount / target_amount * 100, 1) AS progress
                FROM financial_goals WHERE user_id=%s
            """, (session["user_id"],))
            goal_rows = cur.fetchall()
            cur.close()

            for g in goal_rows:
                progress = float(g["progress"] or 0)
                if progress >= 100:
                    advice.append({
                        "type":    "success",
                        "title":   f'Goal "{g["name"]}" complete!',
                        "message": f'You have reached your K {float(g["target"]):,.2f} goal for "{g["name"]}". Consider setting a new, bigger goal.',
                        "action":  "Set a new goal",
                        "action_url": "/profile/goals"
                    })
                elif g["deadline"]:
                    days_left = (datetime.strptime(str(g["deadline"]), "%Y-%m-%d") - datetime.now()).days
                    if 0 < days_left <= 30 and progress < 80:
                        advice.append({
                            "type":    "warning",
                            "title":   f'Goal "{g["name"]}" deadline approaching',
                            "message": f'You are {progress}% toward your K {float(g["target"]):,.2f} goal with only {days_left} days left. You need to save K {float(g["target"]) - float(g["saved"]):,.2f} more.',
                            "action":  "Update goal progress",
                            "action_url": "/profile/goals"
                        })
        except Exception as e:
            print(f"[ADVICE GOALS ERROR] {e}")

    # ── 6. No income recorded tip ───────────────────────────────────
    if total_income == 0 and total_expenses > 0:
        advice.append({
            "type":    "tip",
            "title":   "No income recorded",
            "message": "You have expense transactions but no income recorded. Add your salary or other income so IFMS can calculate your savings rate and generate accurate budget recommendations.",
            "action":  "Add income transaction",
            "action_url": "/transactions/add"
        })

    # ── Cap at 6 items to avoid overwhelming the user ───────────────
    return advice[:6]
