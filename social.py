"""
social.py — Financial Tips Feed (Community Module)
====================================================
Features:
  - Public financial tips feed (lightweight, no infinite scroll bloat)
  - Post, like, reply to tips
  - User-to-user follow system
  - Verified account badges
  - Passkey (WebAuthn) registration & authentication
"""

import os, json, base64, hashlib, secrets
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from auth import login_required, log_event

social_bp  = Blueprint("social", __name__)
_mysql     = None


def init_social(mysql_instance):
    global _mysql
    _mysql = mysql_instance


# ── Helper ────────────────────────────────────────────────────────────

def _uid():
    return session.get("user_id")


def _get_user(uid=None):
    uid = uid or _uid()
    cur = _mysql.connection.cursor()
    cur.execute(
        "SELECT id, name, avatar, is_verified, bio FROM users WHERE id=%s", (uid,)
    )
    u = cur.fetchone()
    cur.close()
    return u


# ─────────────────────────────────────────────────────────────────────
#  TIPS FEED
# ─────────────────────────────────────────────────────────────────────

@social_bp.route("/feed")
@login_required
def feed():
    uid  = _uid()
    cur  = _mysql.connection.cursor()
    # Load tips + author info + like count + whether current user liked
    cur.execute("""
        SELECT
            t.id, t.body, t.created_at, t.tip_type,
            u.id AS author_id, u.name AS author_name,
            u.avatar AS author_avatar, u.is_verified,
            COUNT(DISTINCT tl.id)                       AS like_count,
            MAX(CASE WHEN tl.user_id = %s THEN 1 ELSE 0 END) AS i_liked,
            COUNT(DISTINCT tr.id)                       AS reply_count
        FROM tips t
        JOIN users u ON u.id = t.user_id
        LEFT JOIN tip_likes tl ON tl.tip_id = t.id
        LEFT JOIN tip_replies tr ON tr.tip_id = t.id
        GROUP BY t.id
        ORDER BY t.created_at DESC
        LIMIT 50
    """, (uid,))
    tips = cur.fetchall()
    cur.close()
    return render_template("social/feed.html",
                           tips=tips,
                           user_name=session.get("user_name", ""),
                           uid=uid)


@social_bp.route("/feed/post", methods=["POST"])
@login_required
def post_tip():
    uid     = _uid()
    body    = request.form.get("body", "").strip()
    tip_type = request.form.get("tip_type", "tip").strip()
    if not body or len(body) > 500:
        flash("Tip must be 1–500 characters.", "danger")
        return redirect(url_for("social.feed"))
    if tip_type not in ("tip", "question", "milestone"):
        tip_type = "tip"
    cur = _mysql.connection.cursor()
    cur.execute(
        "INSERT INTO tips (user_id, body, tip_type) VALUES (%s,%s,%s)",
        (uid, body, tip_type)
    )
    _mysql.connection.commit()
    cur.close()
    log_event(_mysql, "TIP_POST", uid)
    flash("Tip posted! 🎉", "success")
    return redirect(url_for("social.feed"))


@social_bp.route("/feed/tip/<int:tip_id>/like", methods=["POST"])
@login_required
def like_tip(tip_id):
    uid = _uid()
    cur = _mysql.connection.cursor()
    cur.execute("SELECT id FROM tip_likes WHERE tip_id=%s AND user_id=%s", (tip_id, uid))
    existing = cur.fetchone()
    if existing:
        cur.execute("DELETE FROM tip_likes WHERE tip_id=%s AND user_id=%s", (tip_id, uid))
        liked = False
    else:
        cur.execute("INSERT INTO tip_likes (tip_id, user_id) VALUES (%s,%s)", (tip_id, uid))
        liked = True
    _mysql.connection.commit()
    cur.execute("SELECT COUNT(*) AS c FROM tip_likes WHERE tip_id=%s", (tip_id,))
    count = cur.fetchone()["c"]
    cur.close()
    return jsonify({"liked": liked, "count": count})


@social_bp.route("/feed/tip/<int:tip_id>/reply", methods=["POST"])
@login_required
def reply_tip(tip_id):
    uid  = _uid()
    body = request.form.get("body", "").strip()
    if not body or len(body) > 300:
        return jsonify({"error": "Reply must be 1–300 characters."}), 400
    cur = _mysql.connection.cursor()
    cur.execute(
        "INSERT INTO tip_replies (tip_id, user_id, body) VALUES (%s,%s,%s)",
        (tip_id, uid, body)
    )
    _mysql.connection.commit()
    reply_id = cur.lastrowid
    cur.execute("""
        SELECT r.id, r.body, r.created_at,
               u.name AS author_name, u.avatar AS author_avatar, u.is_verified
        FROM tip_replies r
        JOIN users u ON u.id = r.user_id
        WHERE r.id=%s
    """, (reply_id,))
    reply = cur.fetchone()
    cur.close()
    return jsonify({
        "id":          reply["id"],
        "body":        reply["body"],
        "author_name": reply["author_name"],
        "is_verified": bool(reply["is_verified"]),
        "created_at":  str(reply["created_at"]),
    })


@social_bp.route("/feed/tip/<int:tip_id>/replies")
@login_required
def get_replies(tip_id):
    cur = _mysql.connection.cursor()
    cur.execute("""
        SELECT r.id, r.body, r.created_at,
               u.name AS author_name, u.avatar, u.is_verified
        FROM tip_replies r
        JOIN users u ON u.id = r.user_id
        WHERE r.tip_id=%s
        ORDER BY r.created_at ASC
    """, (tip_id,))
    replies = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":          r["id"],
        "body":        r["body"],
        "author_name": r["author_name"],
        "is_verified": bool(r["is_verified"]),
        "created_at":  str(r["created_at"]),
    } for r in replies])


# ─────────────────────────────────────────────────────────────────────
#  USER-TO-USER: FOLLOW / UNFOLLOW
# ─────────────────────────────────────────────────────────────────────

@social_bp.route("/user/<int:target_id>/follow", methods=["POST"])
@login_required
def follow(target_id):
    uid = _uid()
    if uid == target_id:
        return jsonify({"error": "Cannot follow yourself"}), 400
    cur = _mysql.connection.cursor()
    cur.execute(
        "SELECT id FROM follows WHERE follower_id=%s AND followed_id=%s",
        (uid, target_id)
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "DELETE FROM follows WHERE follower_id=%s AND followed_id=%s",
            (uid, target_id)
        )
        following = False
    else:
        cur.execute(
            "INSERT INTO follows (follower_id, followed_id) VALUES (%s,%s)",
            (uid, target_id)
        )
        following = True
    _mysql.connection.commit()
    cur.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE followed_id=%s", (target_id,)
    )
    count = cur.fetchone()["c"]
    cur.close()
    return jsonify({"following": following, "followers": count})


@social_bp.route("/user/<int:uid>/profile")
@login_required
def user_profile(uid):
    me  = _uid()
    cur = _mysql.connection.cursor()
    cur.execute(
        "SELECT id,name,avatar,is_verified,bio,created_at FROM users WHERE id=%s", (uid,)
    )
    target = cur.fetchone()
    if not target:
        flash("User not found.", "danger")
        return redirect(url_for("social.feed"))
    cur.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE followed_id=%s", (uid,)
    )
    followers = cur.fetchone()["c"]
    cur.execute(
        "SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (uid,)
    )
    following = cur.fetchone()["c"]
    cur.execute(
        "SELECT id FROM follows WHERE follower_id=%s AND followed_id=%s", (me, uid)
    )
    i_follow = bool(cur.fetchone())
    cur.execute("""
        SELECT t.id, t.body, t.tip_type, t.created_at,
               COUNT(DISTINCT tl.id) AS like_count
        FROM tips t
        LEFT JOIN tip_likes tl ON tl.tip_id = t.id
        WHERE t.user_id=%s
        GROUP BY t.id ORDER BY t.created_at DESC LIMIT 20
    """, (uid,))
    tips = cur.fetchall()
    cur.close()
    return render_template("social/user_profile.html",
                           target=target, tips=tips,
                           followers=followers, following_count=following,
                           i_follow=i_follow,
                           user_name=session.get("user_name", ""),
                           me=me)


# ─────────────────────────────────────────────────────────────────────
#  PROFILE PICTURE UPLOAD
# ─────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_AVATAR_SIZE    = 3 * 1024 * 1024  # 3 MB


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@social_bp.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    uid  = _uid()
    file = request.files.get("avatar")
    if not file or file.filename == "":
        return jsonify({"error": "No file provided"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "Only PNG, JPG, GIF, WEBP allowed"}), 400

    data = file.read()
    if len(data) > MAX_AVATAR_SIZE:
        return jsonify({"error": "File too large (max 3 MB)"}), 400

    ext      = file.filename.rsplit(".", 1)[1].lower()
    filename = f"avatar_{uid}_{secrets.token_hex(6)}.{ext}"
    save_dir = os.path.join(os.path.dirname(__file__), "static", "uploads", "avatars")
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, filename)
    with open(filepath, "wb") as f:
        f.write(data)

    # Remove old avatar file if it exists
    cur = _mysql.connection.cursor()
    cur.execute("SELECT avatar FROM users WHERE id=%s", (uid,))
    old = cur.fetchone()
    if old and old["avatar"]:
        old_path = os.path.join(save_dir, old["avatar"])
        if os.path.exists(old_path):
            os.remove(old_path)

    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, uid))
    _mysql.connection.commit()
    cur.close()
    log_event(_mysql, "AVATAR_UPLOAD", uid)
    return jsonify({"url": url_for("static", filename=f"uploads/avatars/{filename}")})


# ─────────────────────────────────────────────────────────────────────
#  PASSKEY (WebAuthn) — No external library required
#  Uses only: Python stdlib + cryptography (already a Flask dependency)
# ─────────────────────────────────────────────────────────────────────

import struct

try:
    import cbor2
    CBOR2_OK = True
except ImportError:
    CBOR2_OK = False

try:
    from cryptography.hazmat.primitives.asymmetric.ec import (
        ECDSA, EllipticCurvePublicKey, SECP256R1,
        EllipticCurvePublicNumbers
    )
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPublicKey, RSAPublicNumbers
    )
    from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.exceptions import InvalidSignature
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

RP_NAME = "NewGen: Financial Tracker"

def _get_rp_id():
    """Derive RP_ID from the current request host (strips port)."""
    env = os.environ.get("RP_ID")
    if env:
        return env
    host = request.host  # e.g. "localhost:5000" or "127.0.0.1:5000"
    return host.split(":")[0]   # strip port -> "localhost" or "127.0.0.1"

def _get_origin():
    """Derive ORIGIN from the current request."""
    env = os.environ.get("ORIGIN")
    if env:
        return env
    return request.host_url.rstrip("/")  # e.g. "http://127.0.0.1:5000"


def _b64d(s):
    """Decode base64url or standard base64."""
    s = s.replace("-", "+").replace("_", "/")
    return base64.b64decode(s + "==")


def _b64u(b):
    """Encode to base64url (no padding)."""
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _parse_cose_key(cose_bytes):
    """Parse a COSE public key and return a cryptography public key object."""
    cose = cbor2.loads(cose_bytes)
    kty = cose.get(1)
    if kty == 2:  # EC2
        crv = cose.get(-1)
        x   = cose.get(-2)
        y   = cose.get(-3)
        if crv != 1:
            raise ValueError(f"Unsupported EC curve: {crv}")
        # Uncompressed point format
        pub_bytes = b"\x04" + x + y
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePublicNumbers, SECP256R1
        )
        nums = EllipticCurvePublicNumbers(
            x=int.from_bytes(x, "big"),
            y=int.from_bytes(y, "big"),
            curve=SECP256R1()
        )
        return nums.public_key(default_backend())
    elif kty == 3:  # RSA
        n = cose.get(-1)
        e = cose.get(-2)
        from cryptography.hazmat.primitives.asymmetric.rsa import (
            RSAPublicNumbers
        )
        nums = RSAPublicNumbers(
            e=int.from_bytes(e, "big"),
            n=int.from_bytes(n, "big")
        )
        return nums.public_key(default_backend())
    raise ValueError(f"Unsupported COSE key type: {kty}")


def _parse_auth_data(auth_data):
    """Parse WebAuthn authenticator data."""
    rp_id_hash = auth_data[:32]
    flags      = auth_data[32]
    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    result = {"rp_id_hash": rp_id_hash, "flags": flags, "sign_count": sign_count,
              "cred_id": None, "cose_key": None}
    if len(auth_data) > 37 and (flags & 0x40):  # attested credential data
        aaguid    = auth_data[37:53]
        id_len    = struct.unpack(">H", auth_data[53:55])[0]
        cred_id   = auth_data[55:55 + id_len]
        cose_key  = auth_data[55 + id_len:]
        result["cred_id"]  = cred_id
        result["cose_key"] = cose_key
    return result


def _passkey_deps_ok():
    if not CBOR2_OK:
        return False, jsonify({"error": "Missing dependency: run  .venv\Scripts\python.exe -m pip install cbor2"}), 503
    if not CRYPTO_OK:
        return False, jsonify({"error": "Missing dependency: run  .venv\Scripts\python.exe -m pip install cryptography"}), 503
    return True, None, None


@social_bp.route("/passkey/register/begin", methods=["POST"])
@login_required
def passkey_register_begin():
    ok, err, code = _passkey_deps_ok()
    if not ok: return err, code
    uid  = _uid()
    user = _get_user(uid)
    cur  = _mysql.connection.cursor()
    cur.execute("SELECT credential_id FROM passkeys WHERE user_id=%s", (uid,))
    existing = [{"id": row["credential_id"], "type": "public-key"}
                for row in cur.fetchall()]
    cur.close()

    challenge = secrets.token_bytes(32)
    session["passkey_reg_challenge"] = base64.b64encode(challenge).decode()

    rp_id  = _get_rp_id()
    options = {
        "rp":        {"id": rp_id, "name": RP_NAME},
        "user":      {"id": _b64u(str(uid).encode()), "name": user["name"] if user else "user",
                      "displayName": user["name"] if user else "user"},
        "challenge": _b64u(challenge),
        "pubKeyCredParams": [
            {"alg": -7,   "type": "public-key"},   # ES256
            {"alg": -257, "type": "public-key"},   # RS256
        ],
        "timeout": 60000,
        "excludeCredentials": existing,
        "authenticatorSelection": {
            "residentKey": "preferred",
            "userVerification": "preferred",
        },
        "attestation": "none",
    }
    # Store rp_id and origin used so complete() can verify with the same values
    session["passkey_rp_id"] = rp_id
    session["passkey_origin"] = _get_origin()
    return jsonify(options)


@social_bp.route("/passkey/register/complete", methods=["POST"])
@login_required
def passkey_register_complete():
    uid       = _uid()
    challenge = base64.b64decode(session.pop("passkey_reg_challenge", ""))
    data      = request.get_json()

    try:
        rp_id  = session.pop("passkey_rp_id",  _get_rp_id())
        origin = session.pop("passkey_origin", _get_origin())
        # 1. Decode clientDataJSON
        client_data = json.loads(_b64d(data["response"]["clientDataJSON"]))
        assert client_data["type"] == "webauthn.create", f"Wrong type: {client_data['type']}"
        recv_challenge = base64.urlsafe_b64decode(client_data["challenge"] + "==")
        assert recv_challenge == challenge, "Challenge mismatch"
        assert client_data["origin"] == origin, f"Origin mismatch: got {client_data['origin']} expected {origin}"

        # 2. Decode attestationObject
        att_obj   = cbor2.loads(_b64d(data["response"]["attestationObject"]))
        auth_data = _parse_auth_data(att_obj["authData"])

        cred_id  = _b64u(auth_data["cred_id"])
        cose_key = auth_data["cose_key"]
        sign_cnt = auth_data["sign_count"]

        # Store raw COSE key bytes (hex for safe DB storage)
        cose_hex = cose_key.hex()

    except Exception as e:
        return jsonify({"error": f"Registration failed: {e}"}), 400

    device_name = data.get("authenticatorAttachment", "platform")
    cur = _mysql.connection.cursor()
    cur.execute("""
        INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, device_name)
        VALUES (%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE public_key=%s, sign_count=%s
    """, (uid, cred_id, cose_hex, sign_cnt, device_name, cose_hex, sign_cnt))
    _mysql.connection.commit()
    cur.close()
    log_event(_mysql, "PASSKEY_REGISTER", uid)
    return jsonify({"status": "ok"})


@social_bp.route("/passkey/auth/begin", methods=["POST"])
def passkey_auth_begin():
    challenge = secrets.token_bytes(32)
    session["passkey_auth_challenge"] = base64.b64encode(challenge).decode()
    rp_id = _get_rp_id()
    session["passkey_rp_id"] = rp_id
    session["passkey_origin"] = _get_origin()
    options = {
        "challenge":        _b64u(challenge),
        "timeout":          60000,
        "rpId":             rp_id,
        "allowCredentials": [],
        "userVerification": "preferred",
    }
    return jsonify(options)


@social_bp.route("/passkey/auth/complete", methods=["POST"])
def passkey_auth_complete():
    challenge = base64.b64decode(session.pop("passkey_auth_challenge", ""))
    data      = request.get_json()
    cred_id   = data.get("id", "")

    cur = _mysql.connection.cursor()
    cur.execute("""
        SELECT p.user_id, p.public_key, p.sign_count,
               u.name, u.jwt_version
        FROM passkeys p JOIN users u ON u.id=p.user_id
        WHERE p.credential_id=%s
    """, (cred_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({"error": "Passkey not found"}), 404

    try:
        rp_id  = session.pop("passkey_rp_id",  _get_rp_id())
        origin = session.pop("passkey_origin", _get_origin())
        client_data = json.loads(_b64d(data["response"]["clientDataJSON"]))
        assert client_data["type"] == "webauthn.get", f"Wrong type: {client_data['type']}"
        recv_challenge = base64.urlsafe_b64decode(client_data["challenge"] + "==")
        assert recv_challenge == challenge, "Challenge mismatch"
        assert client_data["origin"] == origin, f"Origin mismatch: got {client_data['origin']} expected {origin}"

        auth_data_bytes = _b64d(data["response"]["authenticatorData"])
        auth_data       = _parse_auth_data(auth_data_bytes)

        # Verify RP ID hash
        expected_hash = hashlib.sha256(rp_id.encode()).digest()
        assert auth_data["rp_id_hash"] == expected_hash

        # Rebuild signed data
        client_data_hash = hashlib.sha256(
            _b64d(data["response"]["clientDataJSON"])
        ).digest()
        signed = auth_data_bytes + client_data_hash

        signature    = _b64d(data["response"]["signature"])
        cose_bytes   = bytes.fromhex(row["public_key"])
        pub_key_obj  = _parse_cose_key(cose_bytes)

        if isinstance(pub_key_obj, EllipticCurvePublicKey):
            pub_key_obj.verify(signature, signed, ECDSA(hashes.SHA256()))
        elif isinstance(pub_key_obj, RSAPublicKey):
            pub_key_obj.verify(signature, signed, PKCS1v15(), hashes.SHA256())
        else:
            raise ValueError("Unsupported key type")

    except (AssertionError, InvalidSignature, Exception) as e:
        cur.close()
        return jsonify({"error": f"Authentication failed: {e}"}), 400

    new_count = auth_data["sign_count"]
    cur.execute("UPDATE passkeys SET sign_count=%s WHERE credential_id=%s",
                (new_count, cred_id))
    _mysql.connection.commit()

    from auth import generate_jwt
    uid = row["user_id"]
    session.clear()
    session["user_id"]   = uid
    session["user_name"] = row["name"]
    session["jwt"]       = generate_jwt(uid, row["name"], row.get("jwt_version", 1))
    session.permanent    = True
    cur.close()
    log_event(_mysql, "PASSKEY_LOGIN", uid)
    return jsonify({"status": "ok", "redirect": url_for("dashboard")})


@social_bp.route("/passkey/list")
@login_required
def passkey_list():
    uid = _uid()
    cur = _mysql.connection.cursor()
    cur.execute("""
        SELECT id, device_name, created_at
        FROM passkeys WHERE user_id=%s ORDER BY created_at DESC
    """, (uid,))
    keys = cur.fetchall()
    cur.close()
    return jsonify([{
        "id":          k["id"],
        "device_name": k["device_name"],
        "created_at":  str(k["created_at"]),
    } for k in keys])


@social_bp.route("/passkey/<int:key_id>/delete", methods=["POST"])
@login_required
def passkey_delete(key_id):
    uid = _uid()
    cur = _mysql.connection.cursor()
    cur.execute("DELETE FROM passkeys WHERE id=%s AND user_id=%s", (key_id, uid))
    _mysql.connection.commit()
    cur.close()
    return jsonify({"status": "ok"})
