# step3_run_routing.py

import os
import sys
import pandas as pd
from app_factory import create_app
from run_table_routing_with_checkpoint import run_routing, CHECKPOINT_FILE


DATA_INPUT = "data/sampled_kpi_data.csv"


def main():
    print("=" * 50)
    print("STEP 3: Running Table Routing")
    print("=" * 50)

    if not os.path.exists(DATA_INPUT):
        print(f"\nERROR: Input file not found: {DATA_INPUT}")
        print("Please run step2_load_data.py first.")
        sys.exit(1)

    print(f"\nLoading data from {DATA_INPUT}...")
    df = pd.read_csv(DATA_INPUT)
    print(f"Loaded {len(df)} rows")

    print("\nCreating routing app...")
    app = create_app()

    print("\nStarting routing process...")
    routed_df = run_routing(app, df)

    print("\n" + "-" * 50)
    print("Routing Summary:")
    print("-" * 50)
    print(f"Total rows processed: {len(routed_df)}")

    if "table_name" in routed_df.columns:
        routed_count = routed_df["table_name"].notna().sum()
        print(f"Successfully routed: {routed_count}")
        print(f"Failed to route: {len(routed_df) - routed_count}")

        print("\nRouted table distribution:")
        for table, count in routed_df["table_name"].value_counts().items():
            print(f"  - {table}: {count}")

    print("\n" + "=" * 50)
    print("STEP 3 COMPLETED")
    print("Output saved to: data/checkpoint_results.csv")
    print("=" * 50)


if __name__ == "__main__":
    main()
