"""
Модуль для загрузки конфигурации из JSON-файла.
"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_config: Dict[str, Any] = None


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    global _config
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        _config = json.load(f)
    
    logger.info(f"Конфигурация загружена из {config_path}")
    return _config


def get_config() -> Dict[str, Any]:
    global _config
    if _config is None:
        _config = load_config()
    return _config
