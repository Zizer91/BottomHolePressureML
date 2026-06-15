# conftest.py
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH.
# Теперь Python сможет найти папку 'src'.
sys.path.insert(0, str(Path(__file__).parent))
print(f"PYTHONPATH updated with: {Path(__file__).parent}")
