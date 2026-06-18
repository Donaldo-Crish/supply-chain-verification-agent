import sqlite3
import hashlib
from thefuzz import process
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "supply_chain.db"

CORE_FIELDS = [
    "product_id",
    "name",
    "manufacturer",
    "batch_id",
    "manufacture_date",
    "current_location",
    "status"
]

SYNONYM_MAP = {
    "product_id": ["sku", "productid", "id", "vin", "itemcode", "product_id", "pid"],
    "name": ["productname", "item", "name", "producttype", "product", "component", "itemname"],
    "manufacturer": ["suppliername", "supplier", "brand", "manufacturer", "vendor", "maker"],
    "batch_id": ["batch", "transactionid", "lotnumber", "batchid", "lot", "batchnumber", "groupid"],
    "manufacture_date": ["timestamp", "date", "shippingtime", "manufacturedate", "mfgdate", "dateofmfg", "arrivaldate", "mfg_date"],
    "current_location": ["location", "city", "address", "station", "currentlocation", "site", "place", "checkpoint"],
    "status": ["condition", "inspectionresult", "fraudindicator", "compliance", "status", "result", "verificationstatus", "state"]
}

STATUS_MAP = {
    "pass": "VERIFIED",
    "cleared": "VERIFIED",
    "verified": "VERIFIED",
    "clean": "VERIFIED",
    "ok": "VERIFIED",
    "good": "VERIFIED",
    "fail": "FLAGGED",
    "suspicious": "FLAGGED",
    "flagged": "FLAGGED",
    "failed": "FLAGGED",
    "reject": "FLAGGED",
    "rejected": "FLAGGED",
    "pending": "PENDING",
    "waiting": "PENDING",
    "inreview": "PENDING",
    "hold": "PENDING"
}

def get_connection():
    return sqlite3.connect(str(DB_NAME), check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            name TEXT,
            manufacturer TEXT,
            batch_id TEXT,
            manufacture_date TEXT,
            current_location TEXT,
            status TEXT,
            record_hash TEXT UNIQUE,
            extra_data TEXT,
            added_timestamp TEXT
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_id ON products(product_id)"
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_status ON products(status)"
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_manufacturer ON products(manufacturer)"
    )

    conn.commit()
    conn.close()

def clear_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS products")
    conn.commit()
    conn.close()
    init_db()

def get_best_match(col_name, mapping):
    normalized = str(col_name).lower().replace(" ", "").replace("_", "")
    best_field = None
    best_score = 0

    for core_field, synonyms in mapping.items():
        normalized_synonyms = [s.lower().replace(" ", "").replace("_", "") for s in synonyms]
        result = process.extractOne(normalized, normalized_synonyms)

        if result:
            _, score = result
            if score > best_score:
                best_score = score
                if score > 75:
                    best_field = core_field

    return best_field, best_score

def normalize_status(value):
    cleaned = str(value).lower().strip().replace(" ", "").replace("_", "")
    return STATUS_MAP.get(cleaned, str(value).upper())


def generate_record_hash(product_data):
    raw = (
        str(product_data.get("product_id", "")) +
        str(product_data.get("manufacturer", "")) +
        str(product_data.get("batch_id", "")) +
        str(product_data.get("current_location", "")) +
        str(product_data.get("status", ""))
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def add_product(p):
    conn = get_connection()
    cursor = conn.cursor()

    product_id = str(p.get("product_id", "")).strip()
    name = str(p.get("name", "")).strip()

    if not product_id or not name:
        conn.close()
        return False, "Product ID and Name are required."

    record_hash = generate_record_hash({
        "product_id": product_id,
        "manufacturer": str(p.get("manufacturer", "UNKNOWN")).strip(),
        "batch_id": str(p.get("batch_id", "UNKNOWN")).strip(),
        "current_location": str(p.get("current_location", "UNKNOWN")).strip(),
        "status": normalize_status(p.get("status", "UNKNOWN"))
    })

    try:
        cursor.execute("""
            INSERT INTO products (
                product_id,
                name,
                manufacturer,
                batch_id,
                manufacture_date,
                current_location,
                status,
                record_hash,
                extra_data,
                added_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            name,
            str(p.get("manufacturer", "UNKNOWN")).strip() or "UNKNOWN",
            str(p.get("batch_id", "UNKNOWN")).strip() or "UNKNOWN",
            str(p.get("manufacture_date", "UNKNOWN")).strip() or "UNKNOWN",
            str(p.get("current_location", "UNKNOWN")).strip() or "UNKNOWN",
            normalize_status(p.get("status", "UNKNOWN")),
            record_hash,
            "{}",
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()
        return True, "Product added successfully."

    except sqlite3.IntegrityError:
        conn.close()
        return False, f"Product ID '{product_id}' already exists."

def bulk_insert_products(df, manual_mapping=None):
    conn = get_connection()

    original_cols = df.columns.tolist()
    df = df.copy()
    df.columns = df.columns.str.lower().str.replace(" ", "", regex=False).str.replace("_", "", regex=False)
    col_map_display = dict(zip(df.columns, original_cols))

    rows_to_insert = []
    skipped = 0

    existing_ids = set(
        pd.read_sql_query("SELECT product_id FROM products", conn)["product_id"].astype(str).tolist()
    )

    for _, row in df.iterrows():
        entry = {field: "UNKNOWN" for field in CORE_FIELDS}
        extra_data = {}

        for col in df.columns:
            original_col = col_map_display.get(col, col)
            target = None

            if manual_mapping and original_col in manual_mapping:
                target = manual_mapping[original_col]
                if target == "Ignore":
                    target = None

            if not target:
                best, score = get_best_match(col, SYNONYM_MAP)
                target = best if score > 75 else None

            if target and target in CORE_FIELDS:
                val = row[col]

                if pd.isna(val) or str(val).strip() == "":
                    entry[target] = "UNKNOWN"
                elif target == "status":
                    entry[target] = normalize_status(val)
                else:
                    entry[target] = str(val).strip()
            else:
                extra_data[original_col] = str(row[col]) if not pd.isna(row[col]) else ""

        product_id = str(entry["product_id"]).strip()

        if not product_id or product_id == "UNKNOWN" or product_id in existing_ids:
            skipped += 1
            continue

        entry["extra_data"] = json.dumps(extra_data)
        entry["added_timestamp"] = datetime.now().isoformat()
        entry["record_hash"] = generate_record_hash(entry)

        rows_to_insert.append((
            entry["product_id"],
            entry["name"],
            entry["manufacturer"],
            entry["batch_id"],
            entry["manufacture_date"],
            entry["current_location"],
            entry["status"],
            entry["record_hash"],
            entry["extra_data"],
            entry["added_timestamp"]
            
        ))

        existing_ids.add(product_id)

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO products (
            product_id, name, manufacturer, batch_id, manufacture_date,
            current_location, status, record_hash, extra_data, added_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    conn.close()

    return len(rows_to_insert), skipped

@st.cache_data(ttl=30)
def get_all_products_df():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT product_id, name, manufacturer, batch_id, manufacture_date, current_location, status
        FROM products
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=30)
def get_product_with_extras(product_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM products WHERE product_id = ? LIMIT 1",
        conn,
        params=(product_id,)
    )
    conn.close()

    if df.empty:
        return None

    row = df.iloc[0].to_dict()

    try:
        if row.get("extra_data") and row["extra_data"] != "{}":
            extras = json.loads(row["extra_data"])
            row.update(extras)
    except Exception:
        pass

    row.pop("extra_data", None)
    return row

def get_product_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
    results = dict(cursor.fetchall())
    conn.close()
    return results

init_db()