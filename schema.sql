-- Band Inventory & Equipment Tracking: SQLite schema
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Student (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    email   TEXT
);

CREATE TABLE IF NOT EXISTS Staff (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    role    TEXT CHECK (role IN ('Director', 'Assistant', 'Student Leader')),
    active  INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS Instrument (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,                  -- Flute, Bass Clarinet, ...
    make           TEXT,
    model          TEXT,
    serial_number  TEXT,
    eq_condition   TEXT NOT NULL DEFAULT 'Good'
                   CHECK (eq_condition IN ('Excellent', 'Great', 'Good', 'Poor')),
    quality        TEXT CHECK (quality IN ('Professional', 'Intermediate', 'Beginner')),
    status         TEXT NOT NULL DEFAULT 'Available'
                   CHECK (status IN ('Available', 'Checked Out', 'In Repair', 'Lost', 'Retired'))
);

CREATE TABLE IF NOT EXISTS Equipment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                     -- Mutes, Mics, Drum Sticks, Mallets, ...
    identifier  TEXT,                              -- optional tag or serial
    eq_condition  TEXT NOT NULL DEFAULT 'Good'
                CHECK (eq_condition IN ('Excellent', 'Great', 'Good', 'Poor')),
    status      TEXT NOT NULL DEFAULT 'Available'
                CHECK (status IN ('Available', 'Checked Out', 'In Repair', 'Lost', 'Retired'))
);

CREATE TABLE IF NOT EXISTS UniformPiece (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    part       TEXT NOT NULL
               CHECK (part IN ('Shako', 'Jacket', 'Bibber', 'Gauntlet')),
    number     INTEGER,                            -- blank if the piece isn't numbered
    size       TEXT,                               -- S, M, L, XL, XXL, XXXL; blank if not used
    eq_condition  TEXT NOT NULL DEFAULT 'Good'
               CHECK (eq_condition IN ('Excellent', 'Great', 'Good', 'Poor')),
    status     TEXT NOT NULL DEFAULT 'Available'
               CHECK (status IN ('Available', 'Checked Out', 'In Repair', 'Lost', 'Retired'))
);

-- Folders are picked up by students themselves, so they have no Checkout rows.
CREATE TABLE IF NOT EXISTS Folder (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    number          INTEGER NOT NULL UNIQUE,
    student_id      INTEGER REFERENCES Student(id),  -- blank when the folder isn't assigned
    date_picked_up  TEXT,
    due_date        TEXT
);

CREATE TABLE IF NOT EXISTS Checkout (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type        TEXT NOT NULL
                     CHECK (item_type IN ('Instrument', 'Equipment', 'UniformPiece')),
    item_id          INTEGER NOT NULL,              -- id in the table named by item_type
    student_id       INTEGER NOT NULL REFERENCES Student(id),
    date_checked_out TEXT NOT NULL DEFAULT (date('now')),
    date_checked_in  TEXT,                          -- blank until returned
    checked_out_by   INTEGER NOT NULL REFERENCES Staff(id),
    checked_in_by    INTEGER REFERENCES Staff(id),  -- blank until returned
    notes            TEXT,
    -- a return must record who took it back
    CHECK (date_checked_in IS NULL OR checked_in_by IS NOT NULL)
);

-- Prevents one item from being checked out twice: only one open checkout per item.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_checkout_per_item
    ON Checkout (item_type, item_id)
    WHERE date_checked_in IS NULL;

CREATE INDEX IF NOT EXISTS idx_checkout_student ON Checkout (student_id);
CREATE INDEX IF NOT EXISTS idx_checkout_item    ON Checkout (item_type, item_id);
