"""Create a text-and-tag dataset from processed Exposia annotations."""

import pandas as pd


ann = pd.read_csv("processed/exposia_annotations.csv")

df = ann[["annotated_text", "tag"]].copy()
df = df.dropna()
df = df[df["annotated_text"].str.strip() != ""]

df.to_csv("processed/weakness_dataset.csv", index=False)

print("Weakness dataset created")
print(df.shape)
print(df["tag"].value_counts())
