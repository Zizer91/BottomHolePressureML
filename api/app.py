"""
FastAPI микросервис для прогнозирования забойного давления (BHP).
"""

import logging
import os
import sys
from typing import Dict, Any, List

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

# Импортируем наш pipeline
from src.pipeline import BHPPredictionPipeline

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Создаём приложение FastAPI
app = FastAPI(
    title="BHP Prediction API",
    description="API для прогнозирования забойного давления (BHP)",
    version="1.0.0"
)

# Глобальная переменная для пайплайна
pipeline = None


# ============================================================
# Модели данных
# ============================================================
class WellFeatures(BaseModel):
    choke: float = Field(..., description="Размер штуцера", example=42.5)
    whp: float = Field(..., description="Устьевое давление", example=280.0)
    wht: float = Field(..., description="Устьевая температура", example=65.0)
    gas: float = Field(..., description="Дебит газа", example=150.0)
    cond: float = Field(..., description="Дебит конденсата", example=30.0)
    water: float = Field(..., description="Дебит воды", example=5.0)
    wor: float = Field(..., description="Водо-нефтяной фактор", example=0.1)
    gor: float = Field(..., description="Газо-нефтяной фактор", example=500.0)


class PredictionResponse(BaseModel):
    bhp: float
    status: str = "success"


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


# ============================================================
# Инициализация
# ============================================================
@app.on_event("startup")
async def startup_event():
    global pipeline
    logger.info("Загрузка модели...")
    try:
        pipeline = BHPPredictionPipeline("config.json")
        pipeline.load_model()
        logger.info("Модель успешно загружена")
        logger.info(f"Ожидаемые колонки: {pipeline.feature_columns}")
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}")
        pipeline = None


# ============================================================
# Эндпоинты
# ============================================================
@app.get("/")
async def root():
    return {"message": "BHP Prediction API", "docs": "/docs", "health": "/health"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok" if pipeline else "model_not_loaded",
        model_loaded=pipeline is not None
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(features: WellFeatures):
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Модель не загружена")
    
    try:
        # Преобразуем в DataFrame
        input_data = pd.DataFrame([features.dict()])
        logger.debug(f"Входные данные: {input_data}")
        
        # Маппинг названий колонок (из маленьких в большие)
        column_mapping = {
            'choke': 'Choke',
            'whp': 'WHP',
            'wht': 'WHT',
            'gas': 'Gas',
            'cond': 'Cond',
            'water': 'Water',
            'wor': 'WOR',
            'gor': 'GOR'
        }
        
        # Переименовываем колонки
        input_data = input_data.rename(columns=column_mapping)
        logger.debug(f"После переименования: {input_data.columns.tolist()}")
        
        # Приводим к порядку, ожидаемому моделью
        input_data = input_data[pipeline.feature_columns]
        logger.debug(f"Финальный порядок колонок: {input_data.columns.tolist()}")
        
        # Предсказание
        prediction = pipeline.predict(input_data)
        bhp_value = float(np.round(prediction[0], 1))
        
        logger.info(f"Прогноз: BHP = {bhp_value}")
        return PredictionResponse(bhp=bhp_value)
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/predict_batch")
async def predict_batch(features_list: List[WellFeatures]):
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Модель не загружена")
    
    try:
        # Преобразуем список в DataFrame
        input_data = pd.DataFrame([f.dict() for f in features_list])
        
        # Маппинг колонок
        column_mapping = {
            'choke': 'Choke',
            'whp': 'WHP',
            'wht': 'WHT',
            'gas': 'Gas',
            'cond': 'Cond',
            'water': 'Water',
            'wor': 'WOR',
            'gor': 'GOR'
        }
        input_data = input_data.rename(columns=column_mapping)
        input_data = input_data[pipeline.feature_columns]
        
        # Предсказания
        predictions = pipeline.predict(input_data)
        results = [float(np.round(p, 1)) for p in predictions]
        
        logger.info(f"Пакетный прогноз: {len(results)} объектов")
        return {"predictions": results}
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# Запуск
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
