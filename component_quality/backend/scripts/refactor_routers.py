import re
import os

with open("src/api/main.py", "r") as f:
    content = f.read()

# Define the endpoints to extract
endpoints = [
    ("/predict-weakness", "analysis.py"),
    ("/review", "review.py"),
    ("/generate-feedback", "analysis.py"),
    ("/recommend-resources", "resources.py"),
    ("/knowledge-graph", "knowledge_graph.py"),
    ("/grade-report", "analysis.py"),
    ("/generate-report", "report.py"),
    ("/knowledge-graph-history", "history.py"),
    ("/grading-history", "history.py"),
    ("/analysis-history", "history.py"),
    ("/supervisor-analytics", "analytics.py"),
    ("/grading-analytics", "analytics.py"),
    ("/analyze", "analysis.py")
]

# We will just print them out for now to ensure we can capture them
import ast

class EndpointVisitor(ast.NodeVisitor):
    def __init__(self):
        self.endpoints = []

    def visit_FunctionDef(self, node):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.value.id == 'app':
                    path = decorator.args[0].value
                    self.endpoints.append({
                        "name": node.name,
                        "path": path,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno
                    })
        self.generic_visit(node)

tree = ast.parse(content)
visitor = EndpointVisitor()
visitor.visit(tree)

for ep in visitor.endpoints:
    print(f"Endpoint: {ep['path']} -> Lines {ep['start_line']}-{ep['end_line']}")

