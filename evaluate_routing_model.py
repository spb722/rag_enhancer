# evaluate_routing_model.py

import re
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report
import os


OUTPUT_IMAGE = "data/confusion_matrix.png"


def normalize_name(name):
    if pd.isna(name):
        return None

    name = str(name).upper().strip()
    name = re.sub(r'_\d+$', '', name)
    name = name.replace(" ", "")
    return name


def evaluate(df):

    os.makedirs("data", exist_ok=True)

    print("📊 Evaluating Routing Model...")

    df["actual"] = df["GROUP_NAME"].apply(normalize_name)
    df["predicted"] = df["table_name"].apply(normalize_name)

    df_clean = df.dropna(subset=["actual", "predicted"])

    accuracy = (df_clean["actual"] == df_clean["predicted"]).mean() * 100
    print(f"\n🎯 Accuracy: {accuracy:.2f}%")

    labels = sorted(df_clean["actual"].unique())

    cm = confusion_matrix(
        df_clean["actual"],
        df_clean["predicted"],
        labels=labels
    )

    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)

    plt.figure(figsize=(12, 10))
    disp.plot(xticks_rotation=90)
    plt.title("Confusion Matrix")
    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=300)

    print(f"🖼 Confusion Matrix saved at {OUTPUT_IMAGE}")

    print("\n📈 Classification Report:\n")
    print(classification_report(
        df_clean["actual"],
        df_clean["predicted"]
    ))

    plt.show()