# run_table_routing_with_checkpoint.py

import os
import time
import random
import pandas as pd
from tqdm import tqdm


CHECKPOINT_FILE = "data/checkpoint_results.csv"
SLEEP_MIN = 2
SLEEP_MAX = 3


def run_routing(app, input_df):

    os.makedirs("data", exist_ok=True)

    if os.path.exists(CHECKPOINT_FILE):
        print("🔁 Resuming from checkpoint...")
        final_df = pd.read_csv(CHECKPOINT_FILE)
    else:
        print("🆕 Starting fresh routing...")
        final_df = input_df.copy()
        final_df["table_name"] = None
        final_df["reasoning"] = None

    # Count already processed vs remaining
    already_processed = final_df["table_name"].notna().sum()
    total_rows = len(final_df)
    remaining = total_rows - already_processed

    print(f"📊 Status: {already_processed} done, {remaining} remaining, {total_rows} total")

    if remaining == 0:
        print("✅ All rows already processed!")
        return final_df

    print(f"🚀 Processing {remaining} remaining rows...")

    # Get indices of rows that need processing
    rows_to_process = final_df[final_df["table_name"].isna()].index.tolist()

    processed_count = 0

    # Progress bar only shows REMAINING rows
    for idx in tqdm(rows_to_process, desc="Routing", unit="row"):

        row = final_df.loc[idx]
        user_desc = row["USER_DESCRIPTION"]

        try:
            result = app.invoke({
                "input_statement": user_desc,
                "retrieved_docs": [],
                "evaluation": "",
                "routed_tables": [],
                "reasoning": "",
                "retry_count": 0,
                "rewritten_query": ""
            })

            if result.get("routed_tables"):
                best = max(result["routed_tables"], key=lambda x: x["confidence"])
                table_value = best["table_name"]
            else:
                table_value = None

            reasoning_value = result.get("reasoning", None)

        except Exception as e:
            table_value = None
            reasoning_value = str(e)

        final_df.at[idx, "table_name"] = table_value
        final_df.at[idx, "reasoning"] = reasoning_value

        processed_count += 1

        # Save checkpoint after every row (ensures no data loss on interrupt)
        final_df.to_csv(CHECKPOINT_FILE, index=False)

        # Sleep to prevent rate limit
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

    final_df.to_csv(CHECKPOINT_FILE, index=False)

    print(f"✅ Routing Completed! Processed {processed_count} rows this session.")

    return final_df