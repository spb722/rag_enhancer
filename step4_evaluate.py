# step4_evaluate.py

import os
import sys
import pandas as pd
from evaluate_routing_model import evaluate


DATA_INPUT = "data/checkpoint_results.csv"


def main():
    print("=" * 50)
    print("STEP 4: Evaluating Routing Model")
    print("=" * 50)

    if not os.path.exists(DATA_INPUT):
        print(f"\nERROR: Input file not found: {DATA_INPUT}")
        print("Please run step3_run_routing.py first.")
        sys.exit(1)

    print(f"\nLoading routing results from {DATA_INPUT}...")
    df = pd.read_csv(DATA_INPUT)
    print(f"Loaded {len(df)} rows")

    evaluate(df)

    print("\n" + "=" * 50)
    print("STEP 4 COMPLETED")
    print("Confusion matrix saved to: data/confusion_matrix.png")
    print("=" * 50)


if __name__ == "__main__":
    main()
