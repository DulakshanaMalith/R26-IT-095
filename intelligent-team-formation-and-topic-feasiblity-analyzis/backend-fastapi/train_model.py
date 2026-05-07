import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os

#Define paths
PROCESSED_DIR = "./data/processed"
MODELS_DIR = "./models"
DATA_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")

#Ensure the models directory exists
os.makedirs(MODELS_DIR, exist_ok=True)

print("🧠 Starting Machine Learning Training Pipeline...\n" + "="*50)

#1. Load the Data
if not os.path.exists(DATA_PATH):
    print("❌ Error: Cleaned data not found. Run preprocess.py first.")
    exit()

df = pd.read_csv(DATA_PATH)
print(f"✅ Loaded cleaned data. Training on {len(df)} student profiles.")

#2. Select Features (The inputs) and Target (The output)
# We are using academic history + technical skills to predict the final Exaam Score

features = [
    'Hours_Studied', 'Attendance', 'Previous_Scores', 'Motivation_Level',
    'Skill_React', 'Skill_NodeJS', 'Skill_Python', 'Skill_MongoDB'
]
target = 'Exam_Score'

X = df[features]
y = df[target]

#3 Split the data into "Training" and "Testing" sets (80% train, 20% test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("✂️ Data split into training and testing sets.")

#4 Initialize and Train the Model
print("⚙️ Training the Random Forest Regressor... (This might take a few seconds)")
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

#5 Evaluate the Model
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
r2 = r2_score(y_test, predictions)

print("\n📊 Model Evaluation:")
print(f"    - Mean Absolute Error: {mae:.2f} (On average, predictions are off by this many points)")
print(f"    - R-Squared Score: {r2:.2f} (1.0 is perfect accuracy)")

#6. Save the trained Model to disk
model_path = os.path.join(MODELS_DIR, "feasiblity_model.pkl")
joblib.dump(model, model_path)

print(f"\n Success! Trained model saved to: {model_path}")

print("🎉 Training Pipeline Complete!")