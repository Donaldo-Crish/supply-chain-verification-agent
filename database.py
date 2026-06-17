import sqlite3
from thefuzz import process
import pandas as pd
import json
from datetime import datetime
import streamlit as st

DB_NAME = 'supply_chain.db'
CORE_FIELDS = ['product_id', 'name', 'manufacturer', 'batch_id', 'manufacture_date', 'current_location', 'status']

SYNONYM_MAP = {
    'product_id': ['sku', 'productid', 'id', 'vin', 'itemcode', 'product_id', 'pid'],
    'name': ['productname', 'item', 'name', 'producttype', 'product', 'component', 'itemname'],
    'manufacturer': ['suppliername', 'supplier', 'brand', 'manufacturer', 'vendor', 'maker'],
    'batch_id': ['batch', 'transactionid', 'lotnumber', 'batchid', 'lot', 'batchnumber', 'groupid'],
    'manufacture_date': ['timestamp', 'date', 'shippingtime', 'manufacturedate', 'mfgdate', 'dateofmfg', 'arrivaldate', 'mfg_date'],
    'current_location': ['location', 'city', 'address', 'station', 'currentlocation', 'site', 'place', 'checkpoint'],
    'status': ['condition', 'inspectionresult', 'fraudindicator', 'compliance', 'status', 'result', 'verificationstatus', 'state']
}

STATUS_MAP = {
    'pass': 'VERIFIED', 'cleared': 'VERIFIED', 'verified': 'VERIFIED', 'clean': 'VERIFIED', 'ok': 'VERIFIED', 'good': 'VERIFIED',
    'fail': 'FLAGGED', 'suspicious': 'FLAGGED', 'flagged': 'FLAGGED', 'failed': 'FLAGGED', 'reject': 'FLAGGED', 'rejected': 'FLAGGED',
    'pending': 'PENDING', 'waiting': 'PENDING', 'inreview': 'PENDING', 'hold': 'PENDING'
}

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        product_id TEXT,
        name TEXT,
        manufacturer TEXT,
        batch_id TEXT,
        manufacture_date TEXT,
        current_location TEXT,
        status TEXT,
        extra_data TEXT,
        added_timestamp TEXT
    )''')
    # Add index on product_id for faster lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_id ON products(product_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON products(status)')
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
    # Normalize the column name for matching
    normalized = col_name.lower().replace(' ', '').replace('_', '')
    best_field = None
    best_score = 0
    for core_field, synonyms in mapping.items():
        # Normalize synonyms too
        normalized_synonyms = [s.lower().replace(' ', '').replace('_', '') for s in synonyms]
        match, score = process.extractOne(normalized, normalized_synonyms)
        if score > best_score:
            best_score = score
            if score > 75:
                best_field = core_field
    return best_field, best_score

def normalize_status(value):
    cleaned = str(value).lower().strip().replace(' ', '').replace('_', '')
    return STATUS_MAP.get(cleaned, str(value).upper())

def add_product(p):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)",
        (
            p.get('product_id', 'UNKNOWN'),
            p.get('name', 'UNKNOWN'),
            p.get('manufacturer', 'UNKNOWN'),
            p.get('batch_id', 'UNKNOWN'),
            p.get('manufacture_date', 'UNKNOWN'),
            p.get('current_location', 'UNKNOWN'),
            p.get('status', 'UNKNOWN'),
            "{}",
            datetime.now().isoformat()
        )
    )
    conn.commit()
    conn.close()

def bulk_insert_products(df, manual_mapping=None):
    """
    Insert products from a DataFrame using semantic column mapping.
    Uses INSERT instead of replace to preserve existing data.
    """
    conn = get_connection()
    
    # Normalize column names for matching
    original_cols = df.columns.tolist()
    df.columns = df.columns.str.lower().str.replace(' ', '').str.replace('_', '')
    col_map_display = dict(zip(df.columns, original_cols))  # keep originals for reference
    
    rows_to_insert = []

    for _, row in df.iterrows():
        entry = {field: "UNKNOWN" for field in CORE_FIELDS}
        extra_data = {}

        for col in df.columns:
            # Check manual mapping first (using original col name)
            original_col = col_map_display.get(col, col)
            target = None
            
            if manual_mapping and original_col in manual_mapping:
                target = manual_mapping[original_col]
                if target == "Ignore":
                    target = None
            
            # Fall back to semantic matching
            if not target:
                best, score = get_best_match(col, SYNONYM_MAP)
                target = best if score > 75 else None

            if target and target in CORE_FIELDS:
                val = row[col]
                if pd.isna(val) or str(val).strip() == '':
                    entry[target] = "UNKNOWN"
                elif target == 'status':
                    entry[target] = normalize_status(val)
                else:
                    entry[target] = str(val).strip()
            else:
                # Store unmapped columns in extra_data for AI chat
                extra_data[original_col] = str(row[col]) if not pd.isna(row[col]) else ""

        entry['extra_data'] = json.dumps(extra_data)
        entry['added_timestamp'] = datetime.now().isoformat()
        rows_to_insert.append(tuple(entry[f] for f in CORE_FIELDS) + (entry['extra_data'], entry['added_timestamp']))

    # Use INSERT — don't replace the whole table
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?)",
        rows_to_insert
    )
    conn.commit()
    conn.close()

# ─── CACHED data loader — only reruns when DB actually changes ────────────────
@st.cache_data(ttl=30)  # cache for 30 seconds, auto-refreshes
def get_all_products_df():
    """
    Cached loader — critical for performance with 10k+ rows.
    Only expands extra_data columns if extra_data exists and isn't all empty.
    """
    conn = get_connection()
    # Only fetch core columns for dashboard/charts — fast query
    df = pd.read_sql_query(
        "SELECT product_id, name, manufacturer, batch_id, manufacture_date, current_location, status FROM products",
        conn
    )
    conn.close()
    return df

@st.cache_data(ttl=30)
def get_product_with_extras(product_id):
    """
    Fetch a single product with its extra_data — used only in chat/verify.
    Much faster than loading all 10k rows every time.
    """
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
    
    # Expand extra_data into the dict for AI context
    try:
        if row.get('extra_data') and row['extra_data'] != '{}':
            extras = json.loads(row['extra_data'])
            row.update(extras)
    except:
        pass
    
    del row['extra_data']
    return row

def get_product_count():
    """Lightweight count query — don't load full df just for metrics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM products GROUP BY status")
    results = dict(cursor.fetchall())
    conn.close()
    return results

init_db()