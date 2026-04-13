import json
from server.environment import IncidentEnvironment
from baseline import choose_action

env = IncidentEnvironment()
task_defs = env.tasks()
results = []

for task in task_defs:
    obs = env.reset(task_id=task.task_id, seed=42)
    steps = 0
    while not env.state.done:
        steps += 1
        action = choose_action(obs.model_dump(), env.state.model_dump())
        obs = env.step(action)
    
    score, details = env.grade()
    results.append({"task_id": task.task_id, "score": score, "steps": steps, "details": details})
    print(f"Task: {task.task_id}, Score: {score}, Steps: {steps}")

with open("outputs/task_score_summary.json", "w") as f:
    json.dump(results, f, indent=2)
