# app.py — NewGen Main Application — All Modules + Social/Passkey Update

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
import bcrypt
import os
from config import Config

from auth       import (login_required, api_login_required, log_event,
                        generate_jwt, verify_jwt,
                        generate_mfa_secret, get_mfa_qr_dataurl, verify_totp)
from transactions import transactions_bp, init_transactions
from profile    import profile_bp, init_profile
from advice     import advice_bp, init_advice
from reports    import reports_bp, init_reports
from prediction import prediction_bp, init_prediction
from analysis   import (init_analysis,
                        get_monthly_spending, get_category_summary,
                        get_savings_summary, get_recent_transactions,
                        get_monthly_trend, get_top_categories)
from social     import social_bp, init_social
from reset      import reset_bp, init_reset

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

init_transactions(mysql)
init_analysis(mysql)
init_prediction(mysql)
init_profile(mysql)
init_advice(mysql)
init_reports(mysql)
init_social(mysql)
init_reset(mysql)

app.register_blueprint(transactions_bp)
app.register_blueprint(prediction_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(advice_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(social_bp)
app.register_blueprint(reset_bp)

def hash_pw(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def check_pw(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower()
        password=request.form.get("password",""); confirm=request.form.get("confirm","")
        errors=[]
        if not name: errors.append("Full name is required.")
        if not email or "@" not in email: errors.append("Valid email required.")
        if len(password)<8: errors.append("Password must be ≥ 8 characters.")
        if password!=confirm: errors.append("Passwords do not match.")
        if errors:
            for e in errors: flash(e,"danger")
            return render_template("auth/register.html",name=name,email=email)
        cur=mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s",(email,))
        if cur.fetchone():
            cur.close(); flash("Email already registered.","danger")
            return render_template("auth/register.html",name=name,email=email)
        cur.execute("INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",(name,email,hash_pw(password)))
        mysql.connection.commit(); uid=cur.lastrowid; cur.close()
        log_event(mysql,"REGISTER",uid,f"email={email}")
        session["user_id"]=uid; session["user_name"]=name; session.permanent=True
        flash(f"Welcome to IFMS, {name}! Your account is ready.","success")
        return redirect(url_for("dashboard"))
    return render_template("auth/register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not email or not password:
            flash("Email and password are required.","danger")
            return render_template("auth/login.html",email=email)
        cur=mysql.connection.cursor()
        cur.execute("SELECT id,name,password,mfa_enabled,mfa_secret,jwt_version FROM users WHERE email=%s",(email,))
        user=cur.fetchone(); cur.close()
        if not user or not check_pw(password,user["password"]):
            log_event(mysql,"LOGIN_FAIL",None,f"email={email}")
            flash("Invalid email or password.","danger")
            return render_template("auth/login.html",email=email)
        if user["mfa_enabled"]:
            session["mfa_pending_id"]=user["id"]; session["mfa_pending_name"]=user["name"]; session["mfa_secret"]=user["mfa_secret"]
            return redirect(url_for("mfa_verify"))
        _complete_login(user)
        return redirect(url_for("dashboard"))
    return render_template("auth/login.html")

def _complete_login(user):
    session.clear()
    session["user_id"]=user["id"]; session["user_name"]=user["name"]
    session["jwt"]=generate_jwt(user["id"],user["name"],user.get("jwt_version",1))
    session.permanent=True
    log_event(mysql,"LOGIN_OK",user["id"])
    flash(f"Welcome back, {user['name']}!","success")

@app.route("/mfa/verify", methods=["GET","POST"])
def mfa_verify():
    if "mfa_pending_id" not in session: return redirect(url_for("login"))
    if request.method=="POST":
        code=request.form.get("code","").strip(); secret=session.get("mfa_secret","")
        if verify_totp(secret,code):
            cur=mysql.connection.cursor()
            cur.execute("SELECT id,name,jwt_version FROM users WHERE id=%s",(session["mfa_pending_id"],))
            user=cur.fetchone(); cur.close()
            session.pop("mfa_pending_id",None); session.pop("mfa_pending_name",None); session.pop("mfa_secret",None)
            _complete_login(user); return redirect(url_for("dashboard"))
        else:
            log_event(mysql,"LOGIN_MFA_FAIL",session.get("mfa_pending_id"))
            flash("Invalid code. Please try again.","danger")
    return render_template("auth/mfa_verify.html",user_name=session.get("mfa_pending_name",""))

@app.route("/mfa/setup", methods=["GET","POST"])
@login_required
def mfa_setup():
    uid=session["user_id"]
    cur=mysql.connection.cursor()
    cur.execute("SELECT email,mfa_enabled,mfa_secret FROM users WHERE id=%s",(uid,))
    user=cur.fetchone(); cur.close()
    if request.method=="POST":
        action=request.form.get("action")
        if action=="enable":
            secret=request.form.get("secret",""); code=request.form.get("code","").strip()
            if not verify_totp(secret,code):
                flash("Code incorrect — please scan the QR code and try again.","danger")
                qr=get_mfa_qr_dataurl(user["email"],secret)
                return render_template("auth/mfa_setup.html",secret=secret,qr_url=qr,mfa_enabled=False,user_name=session.get("user_name",""))
            cur=mysql.connection.cursor()
            cur.execute("UPDATE users SET mfa_secret=%s,mfa_enabled=1 WHERE id=%s",(secret,uid))
            mysql.connection.commit(); cur.close()
            log_event(mysql,"MFA_ENABLE",uid); flash("Two-factor authentication enabled! ✓","success")
            return redirect(url_for("profile.profile"))
        elif action=="disable":
            cur=mysql.connection.cursor()
            cur.execute("UPDATE users SET mfa_enabled=0,mfa_secret=NULL WHERE id=%s",(uid,))
            mysql.connection.commit(); cur.close()
            log_event(mysql,"MFA_DISABLE",uid); flash("Two-factor authentication disabled.","info")
            return redirect(url_for("profile.profile"))
    secret=user["mfa_secret"] if user["mfa_enabled"] else generate_mfa_secret()
    qr=get_mfa_qr_dataurl(user["email"],secret)
    return render_template("auth/mfa_setup.html",secret=secret,qr_url=qr,mfa_enabled=bool(user["mfa_enabled"]),user_name=session.get("user_name",""))

@app.route("/logout")
@login_required
def logout():
    log_event(mysql,"LOGOUT",session.get("user_id"))
    name=session.get("user_name","User"); session.clear()
    flash(f"Goodbye, {name}! You've been logged out.","info")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html",user_name=session["user_name"])

@app.route("/predictions")
@login_required
def predictions_page():
    return render_template("predictions.html",user_name=session["user_name"])

@app.route("/advice")
@login_required
def advice_page():
    return render_template("advice.html",user_name=session["user_name"])

@app.route("/api/monthly-spending")
@api_login_required
def api_monthly_spending(): return jsonify(get_monthly_spending())

@app.route("/api/category-summary")
@api_login_required
def api_category_summary(): return jsonify(get_category_summary())

@app.route("/api/savings")
@api_login_required
def api_savings(): return jsonify(get_savings_summary())

@app.route("/api/recent-transactions")
@api_login_required
def api_recent_transactions(): return jsonify(get_recent_transactions())

@app.route("/api/monthly-trend")
@api_login_required
def api_monthly_trend(): return jsonify(get_monthly_trend())

@app.route("/api/top-categories")
@api_login_required
def api_top_categories(): return jsonify(get_top_categories())

@app.route("/api/token/info")
@api_login_required
def api_token_info():
    token=session.get("jwt",""); payload=verify_jwt(token) if token else None
    if payload:
        return jsonify({"user_id":payload["sub"],"name":payload["name"],"issued":payload["iat"],"expires":payload["exp"],"version":payload["ver"]})
    return jsonify({"error":"No valid JWT in session"}),400

@app.route("/debug/db")
@login_required
def debug_db():
    try:
        cur=mysql.connection.cursor(); cur.execute("SHOW TABLES"); rows=cur.fetchall()
        tables=[list(r.values())[0] if isinstance(r,dict) else r[0] for r in rows]
        txn_count=0
        if "transactions" in tables:
            cur.execute("SELECT COUNT(*) AS c FROM transactions WHERE user_id=%s",(session["user_id"],))
            txn_count=cur.fetchone()["c"]
        cur.close()
        return f"<html><body style='font-family:monospace;background:#080b12;color:#f0f4ff;padding:40px;'><h2 style='color:#7c5cfc;'>IFMS Debug</h2><p>User: {session['user_name']} (ID:{session['user_id']})</p><p>Tables: {tables}</p><p>Transactions: {txn_count}</p><br><a href='/dashboard' style='color:#7c5cfc;'>← Dashboard</a></body></html>"
    except Exception as e:
        return f"<pre style='color:#ff6b8a;padding:40px;'>Error: {e}</pre>"

if __name__=="__main__":
    debug=not Config.IS_PRODUCTION
    port=int(os.environ.get("PORT",5000))
    app.run(debug=debug,host="0.0.0.0",port=port)
