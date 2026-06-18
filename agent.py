import pandas as pd
import os
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv
import database

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MODEL_NAME = "llama-3.3-70b-versatile"

def run_groq_completion(messages, max_tokens=300):
    if client is None:
        return (
            "AI analysis is currently unavailable because GROQ_API_KEY is not configured. "
            "The ledger data is still available, but the forensic explanation requires a valid Groq API key."
        )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return (
            "AI analysis is currently unavailable due to a Groq API error. "
            f"Please check the API key, quota, or network connection. Details: {str(e)}"
        )

def load_all_products():
    return database.get_all_products_df()

def load_product_data(product_id):
    return database.get_product_with_extras(product_id)

def trace_journey(product_id):
    data = load_product_data(product_id)
    if not data:
        return []

    try:
        base_date = datetime.fromisoformat(str(data.get("manufacture_date", "2024-01-01")))
    except (TypeError, ValueError):
        base_date = datetime.now() - timedelta(days=30)

    mfg_loc = data.get("current_location", "Unknown Factory")
    if mfg_loc == "UNKNOWN":
        mfg_loc = "Unknown Factory"

    status = data.get("status", "VERIFIED").upper()

    journey = [
        {
            "stage": "Manufacturer",
            "location": mfg_loc,
            "date": base_date.strftime("%Y-%m-%d"),
            "verified": True
        },
        {
            "stage": "Quality Control",
            "location": "Regional Hub",
            "date": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "verified": True
        }
    ]

    if status == "FLAGGED":
        journey.extend([
            {
                "stage": "Transit",
                "location": "Unknown Checkpoint",
                "date": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "verified": False
            },
            {
                "stage": "Distribution",
                "location": "Unregistered Warehouse",
                "date": (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
                "verified": False
            }
        ])
    elif status == "PENDING":
        journey.extend([
            {
                "stage": "Transit",
                "location": "Awaiting Checkpoint Review",
                "date": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "verified": False
            },
            {
                "stage": "Distribution",
                "location": "Pending Final Clearance",
                "date": (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
                "verified": False
            }
        ])
    else:
        journey.extend([
            {
                "stage": "Transit",
                "location": "Verified Checkpoint",
                "date": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                "verified": True
            },
            {
                "stage": "Distribution",
                "location": "Official Retailer",
                "date": (base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
                "verified": True
            }
        ])

    return journey

def get_historical_record_count(product_id):
    try:
        df = pd.read_csv("products.csv")

        if "product_id" not in df.columns:
            return 0

        return int(
            (df["product_id"].astype(str) == str(product_id)).sum()
        )

    except Exception:
        return 0
    
def get_historical_summary(product_id):
    try:
        df = pd.read_csv("products.csv")

        rows = df[df["product_id"].astype(str) == str(product_id)]

        if rows.empty:
            return None

        manufacturers = sorted(
            rows["manufacturer"].dropna().astype(str).unique().tolist()
        )

        locations = sorted(
            rows["current_location"].dropna().astype(str).unique().tolist()
        )

        status_counts = (
            rows["status"]
            .astype(str)
            .value_counts()
            .to_dict()
        )

        return {
            "total_events": len(rows),
            "manufacturers": manufacturers,
            "locations": locations,
            "status_counts": status_counts
        }

    except Exception:
        return None
    
def verify_product(product_id):
    data = load_product_data(product_id)

    history_count = get_historical_record_count(product_id)

    if not data:
        return "Product not found in ledger."

    journey = trace_journey(product_id)
    unverified_stages = [s["stage"] for s in journey if not s["verified"]]

    prompt = f"""You are a senior supply chain forensic analyst. Your job is to investigate product records and explain WHY something is suspicious - not just state that it is.
Product Record:
{data}

Historical Ledger Events:
{history_count}

Chain of Custody Breakdown:
{journey}

Unverified stages: {unverified_stages if unverified_stages else "None - all stages verified"}

Your task:
1. State the verification STATUS clearly: VERIFIED, PENDING, or FLAGGED
2. Explain the SPECIFIC REASON for flagging or pending review
3. Identify the RISK LEVEL: LOW / MEDIUM / HIGH and justify it
4. Give ONE actionable recommendation

Be direct. Be specific. Max 200 words. No fluff."""

    return run_groq_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )

def get_manufacturer_risk_summary():
    conn = database.get_connection()
    query = """
        SELECT manufacturer,
               COUNT(product_id) as total_products,
               SUM(CASE WHEN status = 'FLAGGED' THEN 1 ELSE 0 END) as flagged_count,
               GROUP_CONCAT(CASE WHEN status = 'FLAGGED' THEN product_id END) as flagged_ids
        FROM products
        GROUP BY manufacturer
        HAVING flagged_count > 0
        ORDER BY flagged_count DESC
        LIMIT 10
    """

    try:
        df_summary = pd.read_sql(query, conn)
        conn.close()

        if df_summary.empty:
            return "No manufacturer risk patterns detected at this time.", {}

        patterns_dict = {}
        for _, row in df_summary.iterrows():
            mfr = row["manufacturer"]
            all_ids = str(row["flagged_ids"]).split(",") if row["flagged_ids"] else []
            display_ids = all_ids[:5] + (["..."] if len(all_ids) > 5 else [])

            patterns_dict[mfr] = {
                "flagged_count": int(row["flagged_count"]),
                "total_products": int(row["total_products"]),
                "flag_rate": round((int(row["flagged_count"]) / int(row["total_products"])) * 100, 1),
                "flagged_product_ids": display_ids
            }

        data_text = df_summary[["manufacturer", "total_products", "flagged_count"]].to_string(index=False)

        prompt = f"""You are a Supply Chain Risk Analyst. Analyze this summary table of manufacturers with the highest flagged products:
{data_text}

Provide a brief 2-paragraph executive summary of the risk patterns. Focus on which manufacturers are the biggest liability and what this likely indicates operationally."""

        summary = run_groq_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return summary, patterns_dict

    except Exception as e:
        if "conn" in locals():
            conn.close()
        return f"Error analyzing data: {str(e)}", {}

def chat_about_product(product_id, conversation_history, user_message):
    data = load_product_data(product_id)
    if not data:
        return conversation_history, "That product ID isn't in the ledger. Try another one."

    journey = trace_journey(product_id)
    history_count = get_historical_record_count(product_id)
    unverified_stages = [s["stage"] for s in journey if not s["verified"]]

    system_prompt = f"""You are a supply chain verification specialist with deep forensic knowledge.

You're currently analyzing product {product_id}.

Product record:
{data}

Historical Ledger Events:
{history_count}

Chain of custody:
{journey}

Unverified stages:
{unverified_stages if unverified_stages else "None - all stages verified"}

Answer clearly and specifically.

If asked about:
- historical records
- duplicate product IDs
- number of appearances
- previous ledger events

use the Historical Ledger Events value above.

If a field is available in the product record, use it.

If you don't know something, say so.

Be concise, under 120 words per reply.
"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    assistant_reply = run_groq_completion(messages=messages, max_tokens=300)

    updated_history = conversation_history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply}
    ]

    return updated_history, assistant_reply