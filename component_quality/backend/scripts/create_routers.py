import ast
import os

with open("src/api/main.py", "r") as f:
    content = f.read()
    lines = content.split("\n")

# Define routing map
routes_map = {
    "/predict-weakness": "analysis.py",
    "/generate-feedback": "analysis.py",
    "/grade-report": "analysis.py",
    "/analyze": "analysis.py",
    "/review": "review.py",
    "/recommend-resources": "resources.py",
    "/knowledge-graph": "knowledge_graph.py",
    "/knowledge-graph-history": "knowledge_graph.py",
    "/grading-history": "history.py",
    "/analysis-history": "history.py",
    "/analysis-history/{analysis_id}": "history.py",
    "/supervisor-analytics": "analytics.py",
    "/grading-analytics": "analytics.py",
    "/generate-report": "analysis.py"
}

class EndpointVisitor(ast.NodeVisitor):
    def __init__(self):
        self.endpoints = []

    def visit_FunctionDef(self, node):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.value.id == 'app':
                    path = decorator.args[0].value
                    method = decorator.func.attr
                    self.endpoints.append({
                        "name": node.name,
                        "path": path,
                        "method": method,
                        "start_line": node.lineno - 1, # 0-indexed
                        "end_line": node.end_lineno,
                        "decorator_line": decorator.lineno - 1
                    })
        self.generic_visit(node)

tree = ast.parse(content)
visitor = EndpointVisitor()
visitor.visit(tree)

routers = {}
for ep in visitor.endpoints:
    if ep["path"] == "/": continue
    
    file_name = routes_map[ep["path"]]
    if file_name not in routers:
        routers[file_name] = []
    
    # Extract function text
    # Replace @app.get with @router.get
    func_lines = lines[ep["decorator_line"]:ep["end_line"]]
    func_lines[0] = func_lines[0].replace("@app.", "@router.")
    
    routers[file_name].append("\n".join(func_lines))

# Write routers
os.makedirs("src/api/routers", exist_ok=True)
for file_name, funcs in routers.items():
    router_code = """from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

"""
    router_code += "\n\n".join(funcs)
    with open(f"src/api/routers/{file_name}", "w") as f:
        f.write(router_code)
    print(f"Created {file_name}")

print("All routers created.")
