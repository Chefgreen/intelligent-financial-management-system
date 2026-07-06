import os

class Config:
    SECRET_KEY        = "IFMS_secure_2026_Lunga"
    JWT_SECRET        = "JWT_auth_2026_Greenhead"
    JWT_ALGORITHM     = "HS256"
    JWT_EXPIRY_HOURS  = 8
    MYSQL_HOST        = "localhost"
    MYSQL_USER        = "root"
    MYSQL_PASSWORD    = "PASSWORD"
    MYSQL_DB          = "ifms_db"
    MYSQL_PORT        = 3306
    MYSQL_CURSORCLASS = "DictCursor"
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = "Lax"
    PERMANENT_SESSION_LIFETIME = 3600
    APP_NAME      = "IFMS"
    MFA_ISSUER    = "IFMS Financial"
    IS_PRODUCTION = False
