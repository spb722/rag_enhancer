# load_group_kpi_data.py

import mysql.connector
import pandas as pd
import os


DATA_PATH = "data/sampled_kpi_data.csv"


def load_group_data():

    os.makedirs("data", exist_ok=True)

    # If already extracted, reuse
    if os.path.exists(DATA_PATH):
        print("📂 Loading existing sampled data...")
        return pd.read_csv(DATA_PATH)

    print("🔌 Connecting to MySQL...")

    conn = mysql.connector.connect(
        host="10.0.6.103",
        port=3306,
        user="autopilot_user",
        password="Autopilot@12345",
        database="MAGIK"
    )

    cursor = conn.cursor(dictionary=True)

    groups = [
        "Lifecycle_CDR_6",
        "Audience_Segment_CDR_22",
        "Recharge_Segment_Fct_24",
        "Subscriptions_25",
        "Profile_CDR_Group_26",
        "Common_Segment_Fct_27",
        "Instant_CDR_Group_29"
    ]

    sampled_data = []

    for group in groups:

        print(f"📥 Loading {group}...")

        group_id = int(group.split("_")[-1])

        query = f"""
        SELECT *
        FROM MAGIK.merged_full_kpi m
        WHERE m.profile_name IN (
            SELECT b.profile_name
            FROM MAGIK.RE_BUSINESS_KPIS b
            WHERE b.profile_name IN (
                SELECT r.profile_name
                FROM MAGIK.RE_PROFILE_DESCRIPTION r
                WHERE r.GROUP_ID = {group_id}
            )
        );
        """

        cursor.execute(query)
        grp_data = cursor.fetchall()
        df = pd.DataFrame(grp_data)

        if df.empty:
            print(f"⚠ {group} returned empty.")
            continue

        df_sample = df.sample(frac=0.2, random_state=42)
        df_sample["tag"] = 1
        df_sample["GROUP_NAME"] = group

        sampled_data.append(df_sample)

    cursor.close()
    conn.close()

    final_df = pd.concat(sampled_data, ignore_index=True)

    final_df.to_csv(DATA_PATH, index=False)

    print("✅ Sampled data saved to data/sampled_kpi_data.csv")
    print("📊 Final shape:", final_df.shape)

    return final_df