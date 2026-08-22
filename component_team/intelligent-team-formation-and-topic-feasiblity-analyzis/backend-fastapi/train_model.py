import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import os

# Define paths
PROCESSED_DIR = "./data/processed"
MODELS_DIR = "./models"
DATA_PATH = os.path.join(PROCESSED_DIR, "cleaned_student_factors.csv")

os.makedirs(MODELS_DIR, exist_ok=True)

print("🧠 Starting XGBoost Machine Learning Pipeline...\n" + "="*50)

# 1. Load the Data
if not os.path.exists(DATA_PATH):
    print("❌ Error: Cleaned data not found. Run preprocess.py first.")
    exit()

df = pd.read_csv(DATA_PATH)
print(f"✅ Loaded cleaned data. Training on {len(df)} student profiles.")

# 2. Select Features and Target
features = [
    'Hours_Studied', 'Attendance', 'Previous_Scores', 'Motivation_Level',
    'Skill_React', 'Skill_NodeJS', 'Skill_Python', 'Skill_MongoDB'
]
target = 'Exam_Score'

X = df[features]
y = df[target]

# 3. Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print("✂️ Data split into training and testing sets.")

# 4. Initialize and Train the XGBoost Model
print("⚙️ Training the XGBoost Regressor... (Optimizing gradient trees)")
# We use specific hyper-parameters to prevent overfitting and boost accuracy
model = XGBRegressor(
    n_estimators=150, 
    learning_rate=0.1, 
    max_depth=5, 
    random_state=42
)
model.fit(X_train, y_train)

# 5. Evaluate the Model
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)
r2 = r2_score(y_test, predictions)

print("\n📊 Model Evaluation:")
print(f"   - Mean Absolute Error: {mae:.2f}")
print(f"   - R-squared Score: {r2:.2f}")

# 6. Save the trained model to disk
model_path = os.path.join(MODELS_DIR, "feasibility_model.pkl")
joblib.dump(model, model_path)
print(f"\n💾 Success! XGBoost model saved to: {model_path}")