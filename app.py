"""Band Inventory & Equipment Tracking - Streamlit app.

Setup (once):
    pip install streamlit pandas
    python create_db.py --reset --sample

Run:
    streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="Band Inventory", page_icon="🎺", layout="wide")

if not db.DB_PATH.exists():
    st.error("Database not found. In this folder, run:  python create_db.py --reset --sample")
    st.stop()

TYPE_NAMES = {"Instrument": "Instrument", "UniformPiece": "Uniform piece", "Equipment": "Equipment"}
PAGES = ["Dashboard", "Inventory", "Students", "Check out / in", "Staff"]


# ---------------------------------------------------------------- helpers
def flash(kind, message):
    """Show a message after the next rerun (so it survives st.rerun())."""
    st.session_state["flash"] = (kind, message)


def show_flash():
    note = st.session_state.pop("flash", None)
    if note:
        getattr(st, note[0])(note[1])


def pretty(df):
    """Friendlier column names and no internal id columns for display."""
    df = df.rename(columns={"eq_condition": "condition"})
    return df.drop(columns=[c for c in ("label", "student_id", "out_by_id", "in_by_id") if c in df.columns])


def student_choices():
    """(ids, id -> label). Adds the email when two students share a name."""
    s = db.students()
    dup = s["name"].duplicated(keep=False)
    labels = {int(r.id): (f"{r.name} ({r.email})" if dup[i] else r.name) for i, r in enumerate(s.itertuples())}
    return list(labels.keys()), labels


# ---------------------------------------------------------------- sidebar
st.sidebar.title("🎺 Band Inventory")
page = st.sidebar.radio("Go to", PAGES, label_visibility="collapsed")
st.sidebar.divider()

active_staff = db.staff(active_only=True)
if active_staff.empty:
    st.sidebar.warning("No active staff. Add someone on the Staff page.")
    recorded_by_id = None
else:
    names = active_staff["name"].tolist()
    chosen = st.sidebar.selectbox("Recorded by", names, key="recorded_by")
    recorded_by_id = int(active_staff.loc[active_staff["name"] == chosen, "id"].iloc[0])
    st.sidebar.caption("Used for every check out and check in.")


# -------------------------------------------------------------- dashboard
def page_dashboard():
    st.title("Dashboard")
    show_flash()
    counts = db.status_counts()
    total = counts.groupby("status")["n"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Checked out", int(total.get("Checked Out", 0)))
    c2.metric("Available", int(total.get("Available", 0)))
    c3.metric("In repair", int(total.get("In Repair", 0)))
    c4.metric("Overdue folders", db.overdue_folder_count())

    st.subheader("Items by category and status")
    if not counts.empty:
        counts = counts.assign(category=counts["category"].map(TYPE_NAMES))
        st.bar_chart(counts.pivot_table(index="category", columns="status", values="n", fill_value=0))

    left, right = st.columns(2)
    with left:
        st.subheader("Needs attention")
        attention = db.attention_items()
        if attention.empty:
            st.info("Nothing is in repair or lost.")
        else:
            attention["category"] = attention["category"].map(TYPE_NAMES)
            st.dataframe(attention, hide_index=True)
    with right:
        st.subheader("Recent checkouts")
        recent = db.checkouts().head(10)
        if recent.empty:
            st.info("No checkouts yet.")
        else:
            st.dataframe(recent[["item", "student", "date_checked_out", "date_checked_in"]], hide_index=True)


# -------------------------------------------------------------- inventory
def filters(prefix, with_part=False):
    cols = st.columns([2, 1, 1, 1] if with_part else [2, 1, 1])
    search = cols[0].text_input("Search", key=f"{prefix}_search", placeholder="Name, make, model, serial...")
    status = cols[1].selectbox("Status", ["All"] + db.STATUSES, key=f"{prefix}_status")
    cond = cols[2].selectbox("Condition", ["All"] + db.CONDITIONS, key=f"{prefix}_cond")
    part = cols[3].selectbox("Part", ["All"] + db.UNIFORM_PARTS, key=f"{prefix}_part") if with_part else None
    return dict(
        search=search or None,
        status=None if status == "All" else status,
        condition=None if cond == "All" else cond,
        part=None if part in (None, "All") else part,
    )


def edit_item_form(item_type, items, prefix):
    with st.expander("Change an item's status or condition"):
        if items.empty:
            st.caption("No items to edit.")
            return
        ids = items["id"].astype(int).tolist()
        labels = dict(zip(ids, items["label"]))
        item_id = st.selectbox("Item", ids, format_func=lambda i: labels[i], key=f"{prefix}_edit_item")
        row = items[items["id"] == item_id].iloc[0]
        if row["status"] == "Checked Out":
            st.warning(f"Checked out to {row['held_by']}. Check it in first (Check out / in page).")
            return
        status = st.selectbox("Status", db.MANUAL_STATUSES, index=db.MANUAL_STATUSES.index(row["status"]),
                              key=f"{prefix}_edit_status")
        cond = st.selectbox("Condition", db.CONDITIONS, index=db.CONDITIONS.index(row["eq_condition"]),
                            key=f"{prefix}_edit_cond")
        if st.button("Save changes", key=f"{prefix}_edit_save"):
            try:
                db.update_item(item_type, int(item_id), status, cond)
                flash("success", f"Updated {labels[item_id]}.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def tab_instruments():
    f = filters("inst")
    items = db.list_items("Instrument", **{k: v for k, v in f.items() if k != "part"})
    st.caption(f"{len(items)} instruments")
    st.dataframe(pretty(items), hide_index=True)

    with st.expander("Add an instrument"):
        with st.form("add_instrument", clear_on_submit=True):
            a, b, c = st.columns(3)
            name = a.text_input("Name (e.g. Flute)")
            make = b.text_input("Make")
            model = c.text_input("Model")
            a, b, c, d = st.columns(4)
            serial = a.text_input("Serial number")
            cond = b.selectbox("Condition", db.CONDITIONS, index=2)
            quality = c.selectbox("Quality", db.QUALITIES, index=1)
            status = d.selectbox("Status", db.MANUAL_STATUSES)
            if st.form_submit_button("Add instrument", type="primary"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        db.add_item("Instrument", dict(name=name.strip(), make=make.strip(), model=model.strip(),
                                                       serial_number=serial.strip(), eq_condition=cond,
                                                       quality=quality, status=status))
                        flash("success", f"Added {name.strip()}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not add: {e}")
    edit_item_form("Instrument", items, "inst")


def tab_equipment():
    f = filters("equip")
    items = db.list_items("Equipment", **{k: v for k, v in f.items() if k != "part"})
    st.caption(f"{len(items)} equipment items")
    st.dataframe(pretty(items), hide_index=True)

    with st.expander("Add equipment"):
        with st.form("add_equipment", clear_on_submit=True):
            a, b, c, d = st.columns(4)
            name = a.text_input("Name (e.g. Mic)")
            ident = b.text_input("Identifier / tag")
            cond = c.selectbox("Condition", db.CONDITIONS, index=2)
            status = d.selectbox("Status", db.MANUAL_STATUSES)
            if st.form_submit_button("Add equipment", type="primary"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    db.add_item("Equipment", dict(name=name.strip(), identifier=ident.strip(),
                                                  eq_condition=cond, status=status))
                    flash("success", f"Added {name.strip()}.")
                    st.rerun()
    edit_item_form("Equipment", items, "equip")


def tab_uniforms():
    f = filters("uni", with_part=True)
    items = db.list_items("UniformPiece", **f)
    st.caption(f"{len(items)} uniform pieces")
    st.dataframe(pretty(items), hide_index=True)

    with st.expander("Add a uniform piece"):
        with st.form("add_uniform", clear_on_submit=True):
            a, b, c, d, e = st.columns(5)
            part = a.selectbox("Part", db.UNIFORM_PARTS)
            number = b.number_input("Number (0 = none)", min_value=0, step=1, value=0)
            size = c.selectbox("Size", [""] + db.SIZES)
            cond = d.selectbox("Condition", db.CONDITIONS, index=2)
            status = e.selectbox("Status", db.MANUAL_STATUSES)
            if st.form_submit_button("Add piece", type="primary"):
                db.add_item("UniformPiece", dict(part=part, number=int(number) or None, size=size or None,
                                                 eq_condition=cond, status=status))
                flash("success", f"Added {part}.")
                st.rerun()
    edit_item_form("UniformPiece", items, "uni")


def tab_folders():
    df = db.folders()
    view = st.selectbox("Show", ["All", "Out", "Overdue", "Unassigned"], key="folder_view")
    shown = df if view == "All" else df[df["state"] == view]
    st.caption(f"{len(shown)} folders")
    st.dataframe(shown.drop(columns=["id", "student_id"]), hide_index=True)

    ids, labels = student_choices()
    with st.expander("Assign a folder to a student"):
        free = df[df["state"] == "Unassigned"]
        if free.empty:
            st.caption("Every folder is assigned.")
        else:
            fmap = dict(zip(free["id"].astype(int), free["number"].astype(int)))
            folder_id = st.selectbox("Folder", list(fmap), format_func=lambda i: f"Folder #{fmap[i]}")
            student_id = st.selectbox("Student", ids, format_func=lambda i: labels[i], key="folder_student")
            due = st.date_input("Due date", value=date(date.today().year + (1 if date.today().month > 5 else 0), 5, 14))
            if st.button("Assign folder", type="primary"):
                try:
                    db.assign_folder(int(folder_id), int(student_id), due.isoformat())
                    flash("success", f"Folder #{fmap[folder_id]} assigned to {labels[student_id]}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
    with st.expander("Return a folder"):
        out = df[df["state"] != "Unassigned"]
        if out.empty:
            st.caption("No folders are out.")
        else:
            omap = {int(r.id): f"Folder #{int(r.number)} - {r.student}" for r in out.itertuples()}
            rid = st.selectbox("Folder", list(omap), format_func=lambda i: omap[i], key="folder_return")
            if st.button("Mark returned"):
                db.return_folder(int(rid))
                flash("success", f"{omap[rid]} returned.")
                st.rerun()


def page_inventory():
    st.title("Inventory")
    show_flash()
    t1, t2, t3, t4 = st.tabs(["Instruments", "Equipment", "Uniforms", "Folders"])
    with t1:
        tab_instruments()
    with t2:
        tab_equipment()
    with t3:
        tab_uniforms()
    with t4:
        tab_folders()


# --------------------------------------------------------------- students
def page_students():
    st.title("Students")
    show_flash()
    ids, labels = student_choices()
    if not ids:
        st.info("No students yet.")
    else:
        sid = st.selectbox("Select a student (type to search)", ids, format_func=lambda i: labels[i])
        email = db.students().set_index("id").loc[sid, "email"]
        st.caption(email or "No email on file")

        st.subheader("Everything this student has")
        held = db.checkouts(student_id=int(sid), open_only=True)
        if held.empty:
            st.info("No items checked out.")
        else:
            held = held.assign(item_type=held["item_type"].map(TYPE_NAMES))
            st.dataframe(held[["item_type", "item", "date_checked_out", "checked_out_by"]], hide_index=True)

        uni = db.uniform_held(int(sid))
        jackets = set(uni.loc[uni["part"] == "Jacket", "number"].dropna())
        bibbers = set(uni.loc[uni["part"] == "Bibber", "number"].dropna())
        if jackets and bibbers and jackets != bibbers:
            st.warning(f"Mismatched uniform: jacket {sorted(int(n) for n in jackets)} "
                       f"and bibber {sorted(int(n) for n in bibbers)} come from different sets.")

        folder = db.folders(student_id=int(sid))
        st.subheader("Folder")
        if folder.empty:
            st.info("No folder assigned.")
        else:
            st.dataframe(folder[["number", "date_picked_up", "due_date", "state"]], hide_index=True)

        with st.expander("Full history"):
            st.dataframe(db.checkouts(student_id=int(sid)).drop(columns=["checkout_id", "item_id"]), hide_index=True)

    with st.expander("Add a student"):
        with st.form("add_student", clear_on_submit=True):
            name = st.text_input("Name")
            email = st.text_input("Email")
            if st.form_submit_button("Add student", type="primary"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    db.add_student(name.strip(), email.strip())
                    flash("success", f"Added {name.strip()}.")
                    st.rerun()


# ------------------------------------------------------------ check out/in
def page_checkout():
    st.title("Check out / in")
    show_flash()
    if recorded_by_id is None:
        st.warning("Add an active staff member first (Staff page).")
        return
    st.caption(f"Recording as **{st.session_state.get('recorded_by')}** (change in the sidebar).")
    tab_out, tab_in = st.tabs(["Check out", "Check in"])

    with tab_out:
        item_type = st.selectbox("Item type", db.ITEM_TYPES, format_func=TYPE_NAMES.get)
        available = db.list_items(item_type, status="Available")
        ids, labels = student_choices()
        if available.empty:
            st.warning("Nothing in this category is available.")
        elif not ids:
            st.warning("Add a student first.")
        else:
            amap = dict(zip(available["id"].astype(int), available["label"]))
            item_id = st.selectbox(f"Item ({len(amap)} available, type to search)", list(amap),
                                   format_func=lambda i: amap[i])
            student_id = st.selectbox("Student", ids, format_func=lambda i: labels[i], key="out_student")
            notes = st.text_input("Notes (optional)", key="out_notes")
            if st.button("Check out", type="primary"):
                try:
                    db.check_out(item_type, int(item_id), int(student_id), recorded_by_id, notes)
                    flash("success", f"{amap[item_id]} checked out to {labels[student_id]}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    with tab_in:
        open_all = db.checkouts(open_only=True)
        if open_all.empty:
            st.info("Nothing is checked out.")
        else:
            ids, labels = student_choices()
            holders = {int(i): labels[int(i)] for i in sorted(set(
                db.query("SELECT DISTINCT student_id FROM Checkout WHERE date_checked_in IS NULL")["student_id"]))}
            sid = st.selectbox("Student", list(holders), format_func=lambda i: holders[i], key="in_student")
            mine = db.checkouts(student_id=int(sid), open_only=True)
            cmap = dict(zip(mine["checkout_id"].astype(int), mine["item"]))
            picked = st.multiselect("Items to check in", list(cmap), default=list(cmap),
                                    format_func=lambda i: cmap[i])
            new_status = st.radio("Return as", ["Available", "In Repair"], horizontal=True)
            if st.button("Check in", type="primary", disabled=not picked):
                try:
                    for cid in picked:
                        db.check_in(int(cid), recorded_by_id, new_status)
                    flash("success", f"Checked in {len(picked)} item(s) from {holders[sid]}.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


# ------------------------------------------------------------------ staff
def page_staff():
    st.title("Staff")
    show_flash()
    df = db.staff()
    st.dataframe(df.assign(active=df["active"].map({1: "Yes", 0: "No"})).drop(columns=["id"]), hide_index=True)

    with st.expander("Add staff"):
        with st.form("add_staff", clear_on_submit=True):
            name = st.text_input("Name")
            role = st.selectbox("Role", db.ROLES)
            if st.form_submit_button("Add", type="primary"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    db.add_staff(name.strip(), role)
                    flash("success", f"Added {name.strip()}.")
                    st.rerun()

    with st.expander("Activate / deactivate"):
        if df.empty:
            st.caption("No staff yet.")
        else:
            smap = {int(r.id): f"{r.name} ({'active' if r.active else 'inactive'})" for r in df.itertuples()}
            sid = st.selectbox("Person", list(smap), format_func=lambda i: smap[i])
            is_active = bool(df.loc[df["id"] == sid, "active"].iloc[0])
            label = "Deactivate" if is_active else "Activate"
            if st.button(label):
                db.set_staff_active(int(sid), not is_active)
                flash("success", f"{label}d.")
                st.rerun()
            st.caption("Deactivating keeps their name on old records.")


{"Dashboard": page_dashboard, "Inventory": page_inventory, "Students": page_students,
 "Check out / in": page_checkout, "Staff": page_staff}[page]()
