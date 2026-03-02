# step2_load_data.py

from load_group_kpi_data import load_group_data


def main():
    print("=" * 50)
    print("STEP 2: Loading KPI Data")
    print("=" * 50)

    df = load_group_data()

    print("\n" + "-" * 50)
    print("Data Summary:")
    print("-" * 50)
    print(f"Shape: {df.shape}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nGroups in data:")
    if "GROUP_NAME" in df.columns:
        for group, count in df["GROUP_NAME"].value_counts().items():
            print(f"  - {group}: {count} rows")

    print("\nSample rows (first 3):")
    print(df.head(3).to_string())

    print("\n" + "=" * 50)
    print("STEP 2 COMPLETED")
    print("Output saved to: data/sampled_kpi_data.csv")
    print("=" * 50)


if __name__ == "__main__":
    main()
