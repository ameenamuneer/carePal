import os
import shutil
from pathlib import Path

# Delete migration files
for path in Path('.').rglob('migrations/*.py'):
    if path.name != '__init__.py':
        path.unlink()

# Delete db.sqlite3 if exists (using postgres now, but cleanup doesn't hurt)
if os.path.exists("db.sqlite3"):
    os.remove("db.sqlite3")

# Remove __pycache__
os.system("find . -type d -name __pycache__ -exec rm -r {} +")

print("Cleanup complete.")
