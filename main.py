# main.py

from app_factory import create_app
from load_group_kpi_data import load_group_data
from run_table_routing_with_checkpoint import run_routing
from evaluate_routing_model import evaluate


def main():

    print("\n🚀 STEP 1: Creating Routing App...")
    app = create_app()

    print("\n📥 STEP 2: Loading KPI Data...")
    df = load_group_data()

    print("\n🧠 STEP 3: Running Table Routing...")
    routed_df = run_routing(app, df)

    print("\n📊 STEP 4: Evaluating Model...")
    evaluate(routed_df)

    print("\n✅ FULL PIPELINE COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()