"""
auth.py — Module 1: JWT Authentication + MFA (TOTP)
=====================================================
Provides:
  - JWT token generation and verification
  - TOTP-based Multi-Factor Authentication via pyotp
  - Audit logging helpers
  - login_required / api_login_required decorators
"""

import jwt
import pyotp
import qrcode
import io, base64
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import session, request, jsonify, redirect, url_for, flash, current_app

# ── JWT helpers ──────────────────────────────────────────────────────

def generate_jwt(user_id: int, user_name: str, jwt_version: int) -> str:
    """Create a signed JWT token for a user."""
    from config import Config
    payload = {
        "sub":     user_id,
        "name":    user_name,
        "ver":     jwt_version,          # increment in DB to invalidate all tokens
        "iat":     datetime.now(tz=timezone.utc),
        "exp":     datetime.now(tz=timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def verify_jwt(token: str) -> dict | None:
    """
    Decode and verify a JWT token.
    Returns the payload dict, or None if invalid/expired.
    """
    from config import Config
    try:
        return jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── Decorators ───────────────────────────────────────────────────────

def login_required(f):
    """For page routes — checks Flask session (set at login)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def api_login_required(f):
    """
    For JSON API routes — accepts either:
      (a) Flask session cookie (browser), or
      (b) Authorization: Bearer <JWT> header (API clients)
    Returns 401 JSON on failure instead of a redirect.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check Flask session first (normal browser usage)
        if "user_id" in session:
            return f(*args, **kwargs)

        # Fall back to JWT Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token   = auth_header[7:]
            payload = verify_jwt(token)
            if payload:
                # Inject user_id into session-like context for this request
                session["user_id"]   = payload["sub"]
                session["user_name"] = payload["name"]
                return f(*args, **kwargs)

        return jsonify({"error": "Not authenticated. Log in or provide a valid Bearer token.", "redirect": "/login"}), 401
    return decorated


# ── MFA / TOTP helpers ───────────────────────────────────────────────

def generate_mfa_secret() -> str:
    """Generate a new TOTP secret key for a user."""
    return pyotp.random_base32()


def get_mfa_qr_dataurl(email: str, secret: str) -> str:
    """
    Generate a QR code data URL for scanning in Google Authenticator / Authy.
    Returns a base64-encoded PNG as a data: URL.
    """
    from config import Config
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=email,
        issuer_name=Config.MFA_ISSUER
    )
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the user's secret."""
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(str(code).strip(), valid_window=1)  # ±30s tolerance
    except Exception:
        return False


# ── Audit logging ─────────────────────────────────────────────────────

def log_event(mysql, event_type: str, user_id=None, detail: str = None):
    """
    Write a security event to the audit_log table.
    Call this for: LOGIN_OK, LOGIN_FAIL, LOGIN_MFA_FAIL, LOGOUT,
                   REGISTER, PASSWORD_CHANGE, MFA_ENABLE, MFA_DISABLE,
                   TXN_ADD, TXN_DELETE, PROFILE_UPDATE, EXPORT
    """
    try:
        ip = request.remote_addr
        ua = request.headers.get("User-Agent", "")[:255]
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO audit_log (user_id, event_type, ip_address, user_agent, detail)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, event_type, ip, ua, detail))
        mysql.connection.commit()
        cur.close()
    except Exception as e:
        print(f"[AUDIT LOG ERROR] {e}")
