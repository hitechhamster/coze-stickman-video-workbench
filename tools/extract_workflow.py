"""Preserve the exported Coze graph as data and produce a readable inventory."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "backend/app/workflows/coze_original.yaml"
workflow = yaml.safe_load(source.read_text(encoding="utf-8"))
target = ROOT / "backend/app/workflows"
target.mkdir(parents=True, exist_ok=True)
(target / "coze_original.json").write_text(
    json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8"
)

def visit(nodes):
    for node in nodes:
        params = node.get("parameters", {})
        summary = {"id": node["id"], "title": node["title"], "type": node["type"]}
        for key in ("node_inputs", "llmParam", "modelSetting", "prompt", "branches", "batchSize", "concurrentSize"):
            if key in params:
                value = params[key]
                if key in ("node_inputs", "llmParam"):
                    value = {p["name"]: p.get("input", {}).get("value") for p in value}
                summary[key] = value
        print(json.dumps(summary, ensure_ascii=False))
        visit(node.get("nodes", []))

visit(workflow["nodes"])
