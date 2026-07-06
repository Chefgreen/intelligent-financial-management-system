"""
analysis.py — Module 4: Spending Analysis & Dashboard Logic
Auto-creates transactions table on startup.
_fetch() is intentionally exported for use by advice.py and reports.py.
"""

from flask import session
from datetime import datetime

_mysql = None


def init_analysis(mysql_instance):
    global _mysql
    _mysql = mysql_instance
    _ensure_transactions_table()
    _ensure_all_columns()


def _ensure_all_columns():
    """
    Auto-migrate the database on startup.
    Adds any missing columns/tables so the app works even after upgrading.
    Safe to run repeatedly — uses IF NOT EXISTS and ignores duplicate column errors.
    """
    if _mysql is None:
        return

    migrations = [
        # Users table new columns
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone          VARCHAR(30)   DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_salary DECIMAL(12,2) DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS currency       VARCHAR(10)   DEFAULT 'ZMW'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret     VARCHAR(64)   DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled    TINYINT(1)    NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS jwt_version    INT           NOT NULL DEFAULT 1",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",

        # financial_goals table
        """CREATE TABLE IF NOT EXISTS financial_goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(150) NOT NULL,
            target DECIMAL(12,2) NOT NULL,
            saved DECIMAL(12,2) NOT NULL DEFAULT 0,
            deadline DATE DEFAULT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # Patch goals table if it existed without saved/deadline
        "ALTER TABLE financial_goals ADD COLUMN IF NOT EXISTS saved    DECIMAL(12,2) NOT NULL DEFAULT 0",
        "ALTER TABLE financial_goals ADD COLUMN IF NOT EXISTS deadline DATE DEFAULT NULL",

        # audit_log table
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT DEFAULT NULL,
            event_type VARCHAR(60) NOT NULL,
            ip_address VARCHAR(45) DEFAULT NULL,
            user_agent VARCHAR(255) DEFAULT NULL,
            detail TEXT DEFAULT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_audit_user (user_id),
            INDEX idx_audit_type (event_type),
            INDEX idx_audit_time (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # budget_plans table
        """CREATE TABLE IF NOT EXISTS budget_plans (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            month CHAR(7) NOT NULL,
            income_basis DECIMAL(12,2) NOT NULL,
            needs_budget DECIMAL(12,2) NOT NULL,
            wants_budget DECIMAL(12,2) NOT NULL,
            savings_budget DECIMAL(12,2) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_budget_user_month (user_id, month),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]

    for sql in migrations:
        try:
            cur = _mysql.connection.cursor()
            cur.execute(sql)
            _mysql.connection.commit()
            cur.close()
        except Exception as e:
            err = str(e)
            # Ignore "duplicate column" (1060) and "already exists" (1050) — expected on re-runs
            if "1060" in err or "1050" in err or "already exists" in err.lower():
                pass
            else:
                print(f"[MIGRATION] {err[:120]}")

    print("[IFMS] ✓ Database schema up to date")


def _ensure_transactions_table():
    if _mysql is None:
        return
    try:
        cur = _mysql.connection.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                type ENUM('income','expense') NOT NULL,
                category VARCHAR(100) NOT NULL,
                amount DECIMAL(12,2) NOT NULL,
                description VARCHAR(255) DEFAULT NULL,
                date DATE NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_uid_date (user_id, date DESC),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _mysql.connection.commit()
        cur.close()
        print("[IFMS] transactions table ready")
    except Exception as e:
        print(f"[IFMS] table check: {e}")


def _fetch(limit: int = None) -> list:
    """
    Return all transactions for the logged-in user as list of dicts.
    Exported and used by advice.py and reports.py.
    """
    if _mysql is None or "user_id" not in session:
        return []
    try:
        cur = _mysql.connection.cursor()
        q = """
            SELECT type, category,
                   CAST(amount AS CHAR) AS amount,
                   DATE_FORMAT(date,'%%Y-%%m-%%d') AS date,
                   COALESCE(description,'') AS description
            FROM transactions
            WHERE user_id = %s
            ORDER BY date DESC, id DESC
        """
        if limit:
            q += f" LIMIT {int(limit)}"
        cur.execute(q, (session["user_id"],))
        rows = cur.fetchall()
        cur.close()
        if rows and not isinstance(rows[0], dict):
            cols = ["type","category","amount","date","description"]
            rows = [dict(zip(cols, r)) for r in rows]
        return list(rows)
    except Exception as e:
        print(f"[ANALYSIS] fetch error: {e}")
        return []


def get_savings_summary() -> dict:
    rows = _fetch()
    income = expenses = 0.0
    for r in rows:
        amt = float(r["amount"])
        if r["type"] == "income":   income   += amt
        elif r["type"] == "expense": expenses += amt
    net  = income - expenses
    rate = round(net / income * 100, 2) if income > 0 else 0.0
    return {"total_income": round(income,2), "total_expenses": round(expenses,2),
            "net_savings": round(net,2), "savings_rate": rate}


def get_monthly_spending() -> dict:
    rows    = _fetch()
    monthly = {}
    for r in rows:
        key = r["date"][:7]
        if key not in monthly:
            monthly[key] = {"income":0.0,"expenses":0.0}
        amt = float(r["amount"])
        if r["type"] == "income":    monthly[key]["income"]   += amt
        elif r["type"] == "expense": monthly[key]["expenses"] += amt
    labels, inc_data, exp_data = [], [], []
    for m in sorted(monthly):
        labels.append(datetime.strptime(m,"%Y-%m").strftime("%b %Y"))
        inc_data.append(round(monthly[m]["income"],2))
        exp_data.append(round(monthly[m]["expenses"],2))
    return {"labels":labels,"income":inc_data,"expenses":exp_data}


def get_category_summary() -> dict:
    rows = _fetch()
    cats = {}
    for r in rows:
        if r["type"] == "expense":
            cats[r["category"]] = cats.get(r["category"],0.0) + float(r["amount"])
    sc = sorted(cats.items(), key=lambda x:x[1], reverse=True)
    return {"labels":[c[0] for c in sc],"amounts":[round(c[1],2) for c in sc]}


def get_recent_transactions(limit: int = 10) -> list:
    return _fetch(limit=limit)


def get_monthly_trend() -> dict:
    d = get_monthly_spending()
    return {"labels":d["labels"],"expenses":d["expenses"]}


def get_top_categories(top_n: int = 3) -> list:
    s     = get_category_summary()
    total = sum(s["amounts"])
    out   = []
    for i in range(min(top_n, len(s["labels"]))):
        amt = s["amounts"][i]
        out.append({"category":s["labels"][i],"amount":amt,
                    "percentage":round(amt/total*100,1) if total>0 else 0})
    return out
