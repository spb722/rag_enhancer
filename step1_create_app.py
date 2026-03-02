# step1_create_app.py

from app_factory import create_app


def main():
    print("=" * 50)
    print("STEP 1: Creating and Validating Routing App")
    print("=" * 50)

    print("\nCreating routing app...")
    app = create_app()

    print("\nRunning test query to validate LLM connectivity...")
    test_result = app.invoke({
        "input_statement": "total revenue in the last 30 days",
        "retrieved_docs": [],
        "evaluation": "",
        "routed_tables": [],
        "reasoning": "",
        "retry_count": 0,
        "rewritten_query": ""
    })

    if test_result.get("routed_tables"):
        print("\nTest query result:")
        for table in test_result["routed_tables"]:
            print(f"  - {table['table_name']} (confidence: {table['confidence']})")
        print(f"\nReasoning: {test_result.get('reasoning', 'N/A')}")
        print("\nApp creation and validation SUCCESSFUL")
    else:
        print("\nWARNING: Test query returned no routed tables")
        print(f"Evaluation: {test_result.get('evaluation', 'N/A')}")
        print(f"Reasoning: {test_result.get('reasoning', 'N/A')}")

    print("\n" + "=" * 50)
    print("STEP 1 COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    main()
