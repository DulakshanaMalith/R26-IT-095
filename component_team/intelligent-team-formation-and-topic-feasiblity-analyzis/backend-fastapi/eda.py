import pandas as pd
import os

# Define the path to your raw data
data_dir = "./data/raw"

print("🚀 Starting Exploratory Data Analysis (EDA)...\n" + "="*50)

# Check if the directory exists
if not os.path.exists(data_dir):
    print(f"❌ Error: Could not find the directory '{data_dir}'")
    exit()

# Loop through all files in the raw data directory
for filename in os.listdir(data_dir):
    if filename.endswith(".csv"):
        file_path = os.path.join(data_dir, filename)
        
        print(f"\n📊 Analyzing Dataset: {filename}")
        print("-" * 50)
        
        try:
            # Load the dataset
            df = pd.read_csv(file_path)
            
            # 1. Shape of the data
            print(f"Size: {df.shape[0]} rows, {df.shape[1]} columns")
            
            # 2. Quick look at the columns
            print("\nColumns:")
            cols = df.columns.tolist()
            print(cols[:10] + ["..."] if len(cols) > 10 else cols)
            
            # 3. Check for missing values (Nulls)
            missing_data = df.isnull().sum()
            missing_cols = missing_data[missing_data > 0]
            if not missing_cols.empty:
                print("\n⚠️ Missing Values Found:")
                print(missing_cols.to_string())
            else:
                print("\n✅ No missing values detected.")
            
            # 4. Preview the first 2 rows to see formatting
            print("\nPreview (First 2 rows):")
            print(df.head(2).to_string())
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ Error reading {filename}. It might be corrupted or have a weird encoding. Error: {e}")

print("\n✅ EDA Complete!")