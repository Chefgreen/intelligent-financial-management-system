"""
reset.py — Forgot Password / Reset Password
Simple secure flow: enter email → get token → set new password
No email sending required — token shown on screen for local/dev use.
For production, swap the flash message for an actual email send.
"""

import secrets, hashlib
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import bcrypt

reset_bp = Blueprint("reset", __name__)
_mysql   = None


def init_reset(mysql_instance):
    global _mysql
    _mysql = mysql_instance


def _hash_pw(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ── Forgot Password ───────────────────────────────────────────────────

@reset_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or "@" not in email:
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/forgot_password.html", email=email)

        cur = _mysql.connection.cursor()
        cur.execute("SELECT id, name FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            # Generate a secure token valid for 1 hour
            token     = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            expires    = datetime.utcnow() + timedelta(hours=1)

            cur.execute("""
                UPDATE users SET reset_token=%s, reset_expires=%s WHERE id=%s
            """, (token_hash, expires, user["id"]))
            _mysql.connection.commit()

            reset_url = url_for("reset.reset_password", token=token, _external=True)
            # In production: send reset_url by email
            # For dev/local: store in session so we can show it
            session["dev_reset_url"] = reset_url
            session["dev_reset_name"] = user["name"]

        cur.close()
        # Always show success (don't reveal if email exists)
        return redirect(url_for("reset.forgot_sent"))

    return render_template("auth/forgot_password.html")


@reset_bp.route("/forgot-password/sent")
def forgot_sent():
    dev_url  = session.pop("dev_reset_url",  None)
    dev_name = session.pop("dev_reset_name", None)
    return render_template("auth/forgot_sent.html",
                           dev_url=dev_url, dev_name=dev_name)


# ── Reset Password ────────────────────────────────────────────────────

@reset_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    cur        = _mysql.connection.cursor()
    cur.execute("""
        SELECT id, name, reset_expires FROM users
        WHERE reset_token=%s
    """, (token_hash,))
    user = cur.fetchone()

    if not user:
        cur.close()
        flash("This reset link is invalid.", "danger")
        return redirect(url_for("reset.forgot_password"))

    if datetime.utcnow() > user["reset_expires"]:
        cur.close()
        flash("This reset link has expired. Please request a new one.", "danger")
        return redirect(url_for("reset.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm",  "")

        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors: flash(e, "danger")
            cur.close()
            return render_template("auth/reset_password.html",
                                   token=token, name=user["name"])

        cur.execute("""
            UPDATE users SET password=%s, reset_token=NULL, reset_expires=NULL
            WHERE id=%s
        """, (_hash_pw(password), user["id"]))
        _mysql.connection.commit()
        cur.close()

        flash("Password updated! You can now sign in.", "success")
        return redirect(url_for("login"))

    cur.close()
    return render_template("auth/reset_password.html",
                           token=token, name=user["name"])
