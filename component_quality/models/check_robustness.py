import pandas as pd
from pathlib import Path

def main():
    csv_path = Path("experiments/v1_alpha_baseline/weakness_repeated_metrics.csv")
    df = pd.read_csv(csv_path)
    
    wins = (df["macro_f1"] > df["baseline_macro_f1"]).sum()
    ties = (df["macro_f1"] == df["baseline_macro_f1"]).sum()
    losses = (df["macro_f1"] < df["baseline_macro_f1"]).sum()
    
    print(f"Wins: {wins}, Ties: {ties}, Losses: {losses}")
    
    if wins == len(df):
        print("STATEMENT IS TRUE: Model outperforms baseline on all splits.")
    else:
        print("STATEMENT IS FALSE. Needs correction.")

if __name__ == "__main__":
    main()
