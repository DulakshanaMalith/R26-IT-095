import pandas as pd

file_path = "data/raw/datasets/asap2/ASAP2_train_sourcetexts.csv"

try:
    df = pd.read_csv(file_path)

    print("\n✅ Dataset Loaded Successfully!\n")

    print("📌 Columns:")
    print(df.columns.tolist())

    print("\n📌 First 3 rows:")
    print(df.head(3))

except Exception as e:
    print("\n❌ Error loading dataset:")
    print(e)