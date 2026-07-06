"""transactions.py — Module 3: Transaction Management"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import date as date_type
import re

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")
mysql = None

def init_transactions(mysql_instance):
    global mysql
    mysql = mysql_instance

def login_required(f):
    @wraps(f)
    def d(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return d

VALID_CATEGORIES = {
    "income":  ["Salary","Freelance","Business","Investment","Gift","Other"],
    "expense": ["Food","Rent","Transport","Utilities","Healthcare","Education","Entertainment","Shopping","Savings","Other"],
}

def validate(form):
    errors = []
    t   = form.get("type","").strip().lower()
    cat = form.get("category","").strip()
    amt = form.get("amount","").strip()
    desc = form.get("description","").strip()
    dt  = form.get("date","").strip()
    if t not in ("income","expense"): errors.append("Type must be income or expense.")
    if not cat: errors.append("Category is required.")
    amount = None
    try:
        amount = float(amt)
        if amount <= 0: errors.append("Amount must be greater than zero.")
    except (ValueError,TypeError): errors.append("Amount must be a valid number.")
    if len(desc) > 255: errors.append("Description max 255 chars.")
    if not dt: errors.append("Date is required.")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", dt): errors.append("Invalid date format.")
    if errors: return errors, None
    return [], {"type":t,"category":cat,"amount":amount,"description":desc,"date":dt}

@transactions_bp.route("/")
@login_required
def list_transactions():
    uid = session["user_id"]
    cur = mysql.connection.cursor()
    cur.execute("SELECT id,type,category,amount,description,date FROM transactions WHERE user_id=%s ORDER BY date DESC,id DESC",(uid,))
    rows = cur.fetchall()
    cur.close()
    txns = [{"id":r["id"],"type":r["type"],"category":r["category"],"amount":float(r["amount"]),"description":r["description"] or "","date":str(r["date"])} for r in rows]
    ti = sum(r["amount"] for r in txns if r["type"]=="income")
    te = sum(r["amount"] for r in txns if r["type"]=="expense")
    return render_template("transactions/list.html", transactions=txns, total_income=round(ti,2), total_expenses=round(te,2), net_savings=round(ti-te,2), user_name=session.get("user_name",""))

@transactions_bp.route("/add", methods=["GET","POST"])
@login_required
def add_transaction():
    if request.method == "POST":
        errs, cleaned = validate(request.form)
        if errs:
            for e in errs: flash(e,"danger")
            return render_template("transactions/add.html", form=request.form, categories=VALID_CATEGORIES, user_name=session.get("user_name",""))
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO transactions (user_id,type,category,amount,description,date) VALUES (%s,%s,%s,%s,%s,%s)",
                    (session["user_id"],cleaned["type"],cleaned["category"],cleaned["amount"],cleaned["description"],cleaned["date"]))
        mysql.connection.commit(); cur.close()
        flash("Transaction added! ✓","success")
        return redirect(url_for("transactions.list_transactions"))
    return render_template("transactions/add.html", form={}, categories=VALID_CATEGORIES, today=date_type.today().isoformat(), user_name=session.get("user_name",""))

@transactions_bp.route("/edit/<int:txn_id>", methods=["GET","POST"])
@login_required
def edit_transaction(txn_id):
    uid = session["user_id"]
    cur = mysql.connection.cursor()
    cur.execute("SELECT id,type,category,amount,description,date FROM transactions WHERE id=%s AND user_id=%s",(txn_id,uid))
    row = cur.fetchone()
    if not row: cur.close(); flash("Not found.","danger"); return redirect(url_for("transactions.list_transactions"))
    if request.method == "POST":
        errs, cleaned = validate(request.form)
        if errs:
            for e in errs: flash(e,"danger")
            return render_template("transactions/edit.html", txn_id=txn_id, form=request.form, categories=VALID_CATEGORIES, user_name=session.get("user_name",""))
        cur.execute("UPDATE transactions SET type=%s,category=%s,amount=%s,description=%s,date=%s WHERE id=%s AND user_id=%s",
                    (cleaned["type"],cleaned["category"],cleaned["amount"],cleaned["description"],cleaned["date"],txn_id,uid))
        mysql.connection.commit(); cur.close()
        flash("Transaction updated! ✓","success")
        return redirect(url_for("transactions.list_transactions"))
    cur.close()
    pre = {"type":row["type"],"category":row["category"],"amount":float(row["amount"]),"description":row["description"] or "","date":str(row["date"])}
    return render_template("transactions/edit.html", txn_id=txn_id, form=pre, categories=VALID_CATEGORIES, user_name=session.get("user_name",""))

@transactions_bp.route("/delete/<int:txn_id>", methods=["POST"])
@login_required
def delete_transaction(txn_id):
    uid = session["user_id"]
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM transactions WHERE id=%s AND user_id=%s",(txn_id,uid))
    if cur.fetchone():
        cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s",(txn_id,uid))
        mysql.connection.commit(); flash("Transaction deleted.","info")
    cur.close()
    return redirect(url_for("transactions.list_transactions"))