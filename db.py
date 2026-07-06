# db.py — Database helper (uses DictCursor set in config.py)

def execute_query(mysql, query, params=None):
    """
    Run a SELECT and return a list of dicts.
    Requires MYSQL_CURSORCLASS = "DictCursor" in config.py.
    """
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, params or ())
        rows = cur.fetchall()
        cur.close()
        # DictCursor already returns dicts; plain cursor returns tuples.
        # Handle both so the app works regardless.
        if rows and not isinstance(rows[0], dict):
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in rows]
        return list(rows)
    except Exception as e:
        print(f"[DB ERROR] {type(e).__name__}: {e}")
        return []


def execute_write(mysql, query, params=None):
    """Run an INSERT/UPDATE/DELETE. Returns lastrowid or None."""
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, params or ())
        mysql.connection.commit()
        lid = cur.lastrowid
        cur.close()
        return lid
    except Exception as e:
        print(f"[DB WRITE ERROR] {type(e).__name__}: {e}")
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return None
