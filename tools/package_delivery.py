"""Package source, original assets and built UI; exclude credentials and runtimes."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT.parent / "outputs" / "彩色火柴人-Coze本地剪映版.zip"
excluded_directories = {".venv", "node_modules", "__pycache__", ".git", ".claude", "storage", "outputs"}
excluded_names = {".env", "server-state.json", "outputs-workflow-inventory.ndjson"}
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    for file in ROOT.rglob("*"):
        relative = file.relative_to(ROOT)
        if not file.is_file() or excluded_directories.intersection(relative.parts):
            continue
        if file.name in excluded_names or file.suffix in {".db", ".pyc", ".log"} or ".db-" in file.name:
            continue
        archive.write(file, Path("彩色火柴人-Coze本地剪映版") / relative)
print(target)
print(f"{target.stat().st_size / 1024 / 1024:.1f} MiB")
