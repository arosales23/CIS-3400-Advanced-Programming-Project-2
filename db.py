"""Database layer for the Band Inventory app (SQLite).

All SQL lives here so app.py only deals with the interface.
"""
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "band_inventory.db"

ITEM_TYPES = ["Instrument", "UniformPiece", "Equipment"]
STATUSES = ["Available", "Checked Out", "In Repair", "Lost", "Retired"]
# statuses a person may set by hand ("Checked Out" only happens through a checkout)
MANUAL_STATUSES = ["Available", "In Repair", "Lost", "Retired"]
CONDITIONS = ["Excellent", "Great", "Good", "Poor"]
QUALITIES = ["Professional", "Intermediate", "Beginner"]
UNIFORM_PARTS = ["Shako", "Jacket", "Bibber", "Gauntlet"]
SIZES = ["S", "M", "L", "XL", "XXL", "XXXL"]
ROLES = ["Director", "Assistant", "Student Leader"]

# columns that may be written when adding an item (whitelist)
ITEM_COLUMNS = {
    "Instrument": ["name", "make", "model", "serial_number", "eq_condition", "quality", "status"],
    "UniformPiece": ["part", "number", "size", "eq_condition", "status"],
    "Equipment": ["name", "identifier", "eq_condition", "status"],
}

# how each kind of item is described in lists ({a} = table alias)
_LABEL = {
    "Instrument": "{a}.name || COALESCE(' (' || {a}.serial_number || ')', '')",
    "UniformPiece": "{a}.part || COALESCE(' #' || {a}.number, '') || COALESCE(' (' || {a}.size || ')', '')",
    "Equipment": "{a}.name || COALESCE(' (' || {a}.identifier || ')', '')",
}


def _label(item_type, alias):
    return _LABEL[item_type].format(a=alias)


def _table(item_type):
    if item_type not in ITEM_TYPES:
        raise ValueError(f"Unknown item type: {item_type}")
    return item_type


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    with closing(connect()) as conn:
        return pd.read_sql_query(sql, conn, params=list(params))


def _today():
    return date.today().isoformat()


# ---------------------------------------------------------------- dashboard
def status_counts():
    """One row per (category, status) with a count, across all item tables."""
    parts = [f"SELECT '{t}' AS category, status FROM {t}" for t in ITEM_TYPES]
    return query(
        "SELECT category, status, COUNT(*) AS n FROM (" + " UNION ALL ".join(parts) + ") "
        "GROUP BY category, status"
    )


def attention_items():
    """Items that are in repair or lost."""
    parts = []
    for t in ITEM_TYPES:
        parts.append(
            f"SELECT '{t}' AS category, {_label(t, 'i')} AS item, i.eq_condition AS condition, i.status "
            f"FROM {t} i WHERE i.status IN ('In Repair', 'Lost')"
        )
    return query(" UNION ALL ".join(parts) + " ORDER BY status, category, item")


def overdue_folder_count():
    row = query(
        "SELECT COUNT(*) AS n FROM Folder WHERE student_id IS NOT NULL AND due_date < ?",
        (_today(),),
    )
    return int(row["n"].iloc[0])


# ------------------------------------------------------------------- items
def list_items(item_type, status=None, condition=None, search=None, part=None):
    t = _table(item_type)
    sql = f"""
        SELECT x.*, s.name AS held_by
        FROM (SELECT i.*, {_label(t, 'i')} AS label FROM {t} i) x
        LEFT JOIN Checkout c
               ON c.item_type = '{t}' AND c.item_id = x.id AND c.date_checked_in IS NULL
        LEFT JOIN Student s ON s.id = c.student_id
        WHERE 1 = 1"""
    params = []
    if status:
        sql += " AND x.status = ?"
        params.append(status)
    if condition:
        sql += " AND x.eq_condition = ?"
        params.append(condition)
    if part and t == "UniformPiece":
        sql += " AND x.part = ?"
        params.append(part)
    if search:
        like = f"%{search}%"
        if t == "Instrument":
            sql += " AND (x.label LIKE ? OR x.make LIKE ? OR x.model LIKE ?)"
            params += [like, like, like]
        else:
            sql += " AND x.label LIKE ?"
            params.append(like)
    sql += " ORDER BY x.id"
    return query(sql, params)


def add_item(item_type, values):
    t = _table(item_type)
    cols = [c for c in ITEM_COLUMNS[t] if values.get(c) not in (None, "")]
    sql = f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with closing(connect()) as conn, conn:
        conn.execute(sql, [values[c] for c in cols])


def update_item(item_type, item_id, status, condition):
    """Change status/condition by hand. Checked-out items must be checked in first."""
    t = _table(item_type)
    if status not in MANUAL_STATUSES:
        raise ValueError("Status can only be set to Available, In Repair, Lost or Retired.")
    if condition not in CONDITIONS:
        raise ValueError("Unknown condition.")
    with closing(connect()) as conn, conn:
        row = conn.execute(f"SELECT status FROM {t} WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("Item not found.")
        if row[0] == "Checked Out":
            raise ValueError("This item is checked out. Check it in first.")
        conn.execute(f"UPDATE {t} SET status = ?, eq_condition = ? WHERE id = ?",
                     (status, condition, item_id))


# --------------------------------------------------------------- checkouts
def _checkout_base():
    selects = []
    for t in ITEM_TYPES:
        selects.append(
            f"""SELECT c.id AS checkout_id, c.item_type, c.item_id, {_label(t, 'i')} AS item,
                       c.student_id, c.date_checked_out, c.date_checked_in,
                       c.checked_out_by AS out_by_id, c.checked_in_by AS in_by_id, c.notes
                FROM Checkout c JOIN {t} i ON c.item_type = '{t}' AND i.id = c.item_id"""
        )
    return " UNION ALL ".join(selects)


def checkouts(student_id=None, open_only=False):
    sql = f"""
        SELECT b.checkout_id, b.item_type, b.item_id, b.item, s.name AS student,
               b.date_checked_out, b.date_checked_in,
               so.name AS checked_out_by, si.name AS checked_in_by, b.notes
        FROM ({_checkout_base()}) b
        JOIN Student s ON s.id = b.student_id
        LEFT JOIN Staff so ON so.id = b.out_by_id
        LEFT JOIN Staff si ON si.id = b.in_by_id
        WHERE 1 = 1"""
    params = []
    if student_id is not None:
        sql += " AND b.student_id = ?"
        params.append(student_id)
    if open_only:
        sql += " AND b.date_checked_in IS NULL"
    sql += " ORDER BY b.date_checked_out DESC, b.checkout_id DESC"
    return query(sql, params)


def uniform_held(student_id):
    """Jacket/bibber numbers a student currently holds (to spot mismatched sets)."""
    return query(
        """SELECT u.part, u.number FROM Checkout c
           JOIN UniformPiece u ON c.item_type = 'UniformPiece' AND u.id = c.item_id
           WHERE c.student_id = ? AND c.date_checked_in IS NULL
             AND u.part IN ('Jacket', 'Bibber')""",
        (student_id,),
    )


def check_out(item_type, item_id, student_id, staff_id, notes=None):
    """Create the checkout and mark the item Checked Out, together or not at all."""
    t = _table(item_type)
    try:
        with closing(connect()) as conn, conn:
            row = conn.execute(f"SELECT status FROM {t} WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                raise ValueError("Item not found.")
            if row[0] != "Available":
                raise ValueError(f"This item is {row[0]}, so it can't be checked out.")
            conn.execute(
                """INSERT INTO Checkout
                   (item_type, item_id, student_id, date_checked_out, checked_out_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (t, item_id, student_id, _today(), staff_id, notes or None),
            )
            conn.execute(f"UPDATE {t} SET status = 'Checked Out' WHERE id = ?", (item_id,))
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Could not check out: {e}") from e


def check_in(checkout_id, staff_id, new_status="Available"):
    """Close a checkout and set the item's status (Available, In Repair, ...)."""
    if new_status not in MANUAL_STATUSES:
        raise ValueError("Item must come back as Available, In Repair, Lost or Retired.")
    with closing(connect()) as conn, conn:
        row = conn.execute(
            "SELECT item_type, item_id, date_checked_in FROM Checkout WHERE id = ?",
            (checkout_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Checkout not found.")
        if row[2] is not None:
            raise ValueError("This checkout was already checked in.")
        t = _table(row[0])
        conn.execute(
            "UPDATE Checkout SET date_checked_in = ?, checked_in_by = ? WHERE id = ?",
            (_today(), staff_id, checkout_id),
        )
        conn.execute(f"UPDATE {t} SET status = ? WHERE id = ?", (new_status, row[1]))


# ---------------------------------------------------------------- students
def students():
    return query("SELECT id, name, email FROM Student ORDER BY name")


def add_student(name, email):
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO Student (name, email) VALUES (?, ?)", (name, email or None))


# ------------------------------------------------------------------- staff
def staff(active_only=False):
    sql = "SELECT id, name, role, active FROM Staff"
    if active_only:
        sql += " WHERE active = 1"
    return query(sql + " ORDER BY name")


def add_staff(name, role):
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO Staff (name, role, active) VALUES (?, ?, 1)", (name, role))


def set_staff_active(staff_id, active):
    with closing(connect()) as conn, conn:
        conn.execute("UPDATE Staff SET active = ? WHERE id = ?", (1 if active else 0, staff_id))


# ----------------------------------------------------------------- folders
def folders(student_id=None):
    sql = """SELECT f.id, f.number, s.name AS student, f.student_id,
                    f.date_picked_up, f.due_date,
                    CASE WHEN f.student_id IS NOT NULL AND f.due_date < ? THEN 'Overdue'
                         WHEN f.student_id IS NOT NULL THEN 'Out'
                         ELSE 'Unassigned' END AS state
             FROM Folder f LEFT JOIN Student s ON s.id = f.student_id"""
    params = [_today()]
    if student_id is not None:
        sql += " WHERE f.student_id = ?"
        params.append(student_id)
    return query(sql + " ORDER BY f.number", params)


def assign_folder(folder_id, student_id, due_date):
    with closing(connect()) as conn, conn:
        row = conn.execute("SELECT student_id FROM Folder WHERE id = ?", (folder_id,)).fetchone()
        if row is None:
            raise ValueError("Folder not found.")
        if row[0] is not None:
            raise ValueError("This folder is already assigned.")
        conn.execute(
            "UPDATE Folder SET student_id = ?, date_picked_up = ?, due_date = ? WHERE id = ?",
            (student_id, _today(), due_date, folder_id),
        )


def return_folder(folder_id):
    with closing(connect()) as conn, conn:
        conn.execute(
            "UPDATE Folder SET student_id = NULL, date_picked_up = NULL WHERE id = ?",
            (folder_id,),
        )
