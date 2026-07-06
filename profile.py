"""
profile.py — Module 2: User Profile, Salary, Goals, Passkey Management
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from auth import login_required, log_event

profile_bp = Blueprint("profile", __name__)
_mysql = None

def init_profile(mysql_instance):
    global _mysql
    _mysql = mysql_instance

@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = session["user_id"]
    cur = _mysql.connection.cursor()

    if request.method == "POST":
        name   = request.form.get("name",           "").strip()
        phone  = request.form.get("phone",          "").strip()
        salary = request.form.get("monthly_salary", "").strip()
        curr   = request.form.get("currency",       "ZMW").strip()
        bio    = request.form.get("bio",             "").strip()[:300]

        errors = []
        if not name: errors.append("Name is required.")
        sal_val = None
        if salary:
            try:
                sal_val = float(salary)
                if sal_val < 0: errors.append("Salary cannot be negative.")
            except ValueError: errors.append("Salary must be a number.")

        if errors:
            for e in errors: flash(e, "danger")
        else:
            cur.execute("""
                UPDATE users SET name=%s, phone=%s, monthly_salary=%s, currency=%s, bio=%s
                WHERE id=%s
            """, (name, phone or None, sal_val, curr, bio or None, uid))
            _mysql.connection.commit()
            session["user_name"] = name
            log_event(_mysql, "PROFILE_UPDATE", uid, f"name={name}")
            flash("Profile updated successfully! ✓", "success")
            cur.close()
            return redirect(url_for("profile.profile"))

    cur.execute("""
        SELECT name, email, phone, monthly_salary, currency, mfa_enabled, avatar, bio, is_verified
        FROM users WHERE id=%s
    """, (uid,))
    user = cur.fetchone()

    # Passkeys for this user
    cur.execute("""
        SELECT id, device_name, created_at FROM passkeys WHERE user_id=%s ORDER BY created_at DESC
    """, (uid,))
    passkeys = cur.fetchall()

    cur.close()
    return render_template("profile.html", user=user, passkeys=passkeys,
                           user_name=session.get("user_name", ""))


@profile_bp.route("/profile/goals", methods=["GET", "POST"])
@login_required
def goals():
    uid = session["user_id"]
    cur = _mysql.connection.cursor()

    if request.method == "POST":
        goal_name  = request.form.get("name",     "").strip()
        target_raw = request.form.get("target",   "").strip()
        saved_raw  = request.form.get("saved",    "0").strip()
        deadline   = request.form.get("deadline", "").strip() or None

        errors = []
        if not goal_name: errors.append("Goal name is required.")
        target_v = saved_v = 0.0
        try:
            target_v = float(target_raw); saved_v = float(saved_raw)
            if target_v <= 0: errors.append("Target must be greater than zero.")
            if saved_v < 0: errors.append("Saved amount cannot be negative.")
            if saved_v > target_v: errors.append("Saved cannot exceed the target.")
        except (ValueError, TypeError): errors.append("Target and saved must be valid numbers.")

        if errors:
            for e in errors: flash(e, "danger")
        else:
            cur.execute("""
                INSERT INTO financial_goals (user_id, goal_name, target_amount, saved_amount, deadline)
                VALUES (%s,%s,%s,%s,%s)
            """, (uid, goal_name, target_v, saved_v, deadline))
            _mysql.connection.commit()
            flash(f'Goal "{goal_name}" created! ✓', "success")

    cur.execute("""
        SELECT id,
               goal_name AS name,
               target_amount AS target,
               saved_amount AS saved,
               deadline,
               ROUND(saved_amount/target_amount*100,1) AS progress
        FROM financial_goals WHERE user_id=%s ORDER BY created_at DESC
    """, (uid,))
    goal_list = cur.fetchall()
    cur.close()
    return render_template("goals.html", goals=goal_list, user_name=session.get("user_name", ""))


@profile_bp.route("/profile/goals/<int:gid>/update", methods=["POST"])
@login_required
def update_goal(gid):
    uid = session["user_id"]; saved_in = request.form.get("saved","0").strip()
    try: saved_v = float(saved_in)
    except ValueError:
        flash("Saved amount must be a number.", "danger")
        return redirect(url_for("profile.goals"))
    cur = _mysql.connection.cursor()
    cur.execute("SELECT target_amount FROM financial_goals WHERE id=%s AND user_id=%s",(gid,uid))
    row = cur.fetchone()
    if row:
        target = float(row["target_amount"])
        if saved_v > target: flash("Saved cannot exceed target.","danger")
        elif saved_v < 0: flash("Saved amount cannot be negative.","danger")
        else:
            cur.execute("UPDATE financial_goals SET saved_amount=%s WHERE id=%s AND user_id=%s",(saved_v,gid,uid))
            _mysql.connection.commit(); flash("Goal progress updated! ✓","success")
    else: flash("Goal not found.","danger")
    cur.close()
    return redirect(url_for("profile.goals"))


@profile_bp.route("/profile/goals/<int:gid>/delete", methods=["POST"])
@login_required
def delete_goal(gid):
    uid = session["user_id"]
    cur = _mysql.connection.cursor()
    cur.execute("DELETE FROM financial_goals WHERE id=%s AND user_id=%s",(gid,uid))
    _mysql.connection.commit(); cur.close()
    flash("Goal deleted.","info")
    return redirect(url_for("profile.goals"))


@profile_bp.route("/api/goals-summary")
@login_required
def api_goals_summary():
    uid = session["user_id"]
    cur = _mysql.connection.cursor()
    cur.execute("""
        SELECT goal_name AS name, target_amount AS target, saved_amount AS saved,
               ROUND(saved_amount/target_amount*100,1) AS progress
        FROM financial_goals WHERE user_id=%s ORDER BY progress DESC LIMIT 5
    """, (uid,))
    rows = cur.fetchall()
    cur.execute("SELECT monthly_salary,currency FROM users WHERE id=%s",(uid,))
    user = cur.fetchone(); cur.close()
    return jsonify({
        "goals": list(rows),
        "monthly_salary": float(user["monthly_salary"]) if user and user["monthly_salary"] else None,
        "currency": user["currency"] if user else "ZMW",
    })
