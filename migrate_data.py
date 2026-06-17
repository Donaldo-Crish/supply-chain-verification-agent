import pandas as pd
import os
import time

print("🚀 Step 1: Starting the data translation process...")
start_time = time.time()

if not os.path.exists('trust_chain_dataset.csv'):
    print("❌ Error: trust_chain_dataset.csv not found in this folder!")
else:
    print("📖 Step 2: Loading trust_chain_dataset.csv...")
    raw_df = pd.read_csv('trust_chain_dataset.csv')
    total_rows = len(raw_df)
    print(f"✅ Found {total_rows:,} rows of data to process.")

    # Clean column names by stripping trailing/leading whitespaces
    raw_df.columns = raw_df.columns.str.strip()

    # Find the exact names of the fraud and compliance columns dynamically
    fraud_col = [c for c in raw_df.columns if 'Fraud' in c]
    compliance_col = [c for c in raw_df.columns if 'Compliance' in c]

    if not fraud_col or not compliance_col:
        print("\n❌ Error identifying columns!")
        print(f"Available columns in your file are: {list(raw_df.columns)}")
        print("Please check if you have columns named 'Fraud' or 'Compliance'.")
    else:
        # Grab the first match found
        actual_fraud_name = fraud_col[0]
        actual_compliance_name = compliance_col[0]
        print(f"🔍 Found exact column names: '{actual_fraud_name}' and '{actual_compliance_name}'")

        # 2. Create a blank table for our app's data
        app_df = pd.DataFrame()

        print("⚡ Step 3: Translating and mapping columns...")
        app_df['product_id'] = 'PRD-' + raw_df['Item ID'].astype(str)
        app_df['name'] = 'Component-' + raw_df['Item ID'].astype(str)
        app_df['manufacturer'] = raw_df['Supplier ID']
        app_df['batch_id'] = raw_df['Transaction ID']
        app_df['manufacture_date'] = raw_df['Timestamp']
        app_df['current_location'] = raw_df['Location']

        print("🧠 Step 4: Running automated compliance rules...")
        app_df['status'] = 'VERIFIED'
        
        # Use the dynamic column names we discovered
        flag_condition = (raw_df[actual_fraud_name] == 1) | (raw_df[actual_compliance_name] == 0)
        app_df.loc[flag_condition, 'status'] = 'FLAGGED'

        print("💾 Step 5: Exporting processed data to products.csv...")
        app_df.to_csv('products.csv', index=False)
        
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"🎉 Success! Processed {len(app_df):,} rows in {elapsed:.2f} seconds!")