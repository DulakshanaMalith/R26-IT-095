import joblib, numpy as np, pandas as pd, sys
sys.stdout.reconfigure(encoding='utf-8')

print('=== Integration Test: Model 5 Feature Vector ===')

bundle = joblib.load(r'models\workload_rf.joblib')
model  = bundle['model']
feats  = bundle['features']

print(f'Model expects {len(feats)} features:')
for i, f in enumerate(feats, 1):
    print(f'  {i}. {f}')

print()
print('Simulating: Backend Development (80h) assigned to 3 members...')
print()

effort     = 80.0
task_cat   = 1    # backend = complex
task_cmplx = 2    # 40-80h = medium

members = [
    {'name': 'Dulakshana', 'completion_rate': 0.90, 'current_workload': 0.0, 'avg_effort': 50.0},
    {'name': 'Malith',     'completion_rate': 0.60, 'current_workload': 2.0, 'avg_effort': 35.0},
    {'name': 'Kasun',      'completion_rate': 0.75, 'current_workload': 1.0, 'avg_effort': 45.0},
]

results = []
for m in members:
    feat_df = pd.DataFrame([{
        "task_effort_estimate"    : effort,
        "task_category"           : float(task_cat),
        "task_complexity"         : float(task_cmplx),
        "member_completion_rate"  : m['completion_rate'],
        "member_current_workload" : m['current_workload'],
        "member_avg_effort"       : m['avg_effort'],
        "is_collaborative"        : 0.0
    }])
    prob = model.predict_proba(feat_df)[0][1]
    results.append((m['name'], prob))
    name = m['name']
    cr   = m['completion_rate']
    wl   = m['current_workload']
    print(f'  {name:15s} -> P(on_time) = {prob*100:.1f}%  | workload={wl} tasks, completion_rate={cr}')

best_name, best_prob = max(results, key=lambda x: x[1])
print()
print(f'  BEST MEMBER: {best_name} (confidence: {best_prob*100:.1f}%)')
print()
n_feat = feat_df.shape[1]
print(f'  Feature count: {n_feat} (model expects {len(feats)}) -> MATCH: {n_feat == len(feats)}')
print()
if n_feat == len(feats):
    print('=== Test PASSED - Integration is CORRECT ===')
else:
    print('=== Test FAILED - Feature mismatch! ===')
