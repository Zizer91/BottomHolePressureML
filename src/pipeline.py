"""
Pipeline для прогнозирования забойного давления (BHP).
Оркестрирует весь процесс: загрузка данных -> обучение -> предсказание.
"""

import logging
import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from typing import Optional

from src.data_loader import load_and_preprocess
from src.models import train_stacking_model
from src.config_loader import load_config

logger = logging.getLogger(__name__)


class BHPPredictionPipeline:
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self._setup_logging()
        self.model = None
        self.feature_columns = None
        logger.info("Pipeline инициализирован")
    
    def _setup_logging(self) -> None:
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(level=log_level, format=log_format)
    
    def train(self) -> object:
        logger.info("=" * 50)
        logger.info("НАЧАЛО ОБУЧЕНИЯ МОДЕЛИ")
        logger.info("=" * 50)
        
        try:
            data_config = self.config.get('data', {})
            X_train, y_train, _ = load_and_preprocess(
                data_config.get('train_path', 'data/teach_data.csv'),
                data_config.get('forecast_path', 'data/forecast.csv')
            )
            logger.info(f"Загружено: X_train.shape={X_train.shape}, y_train.shape={y_train.shape}")
            
            self.feature_columns = list(X_train.columns)
            logger.info(f"Признаки: {self.feature_columns}")
            
            training_config = self.config.get('training', {})
            self.model = train_stacking_model(
                X_train, y_train,
                test_size=training_config.get('test_size', 0.25),
                random_state=training_config.get('random_state', 42),
                n_splits=training_config.get('n_splits', 5)
            )
            
            logger.info("Шаг 3: Сохранение модели")
            self._save_model()
            
            logger.info("=" * 50)
            logger.info("ОБУЧЕНИЕ ЗАВЕРШЕНО УСПЕШНО")
            logger.info("=" * 50)
            
            return self.model
            
        except Exception as e:
            logger.error(f"Ошибка при обучении модели: {str(e)}", exc_info=True)
            raise
    
    def _save_model(self) -> None:
        if self.model is None:
            raise ValueError("Модель не обучена. Сначала вызовите train().")
        
        models_config = self.config.get('models', {})
        model_path = models_config.get('model_path', 'models/stacking_model.pkl')
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        model_data = {
            'model': self.model,
            'feature_columns': self.feature_columns,
            'config': self.config,
            'training_date': datetime.now().isoformat()
        }
        joblib.dump(model_data, model_path)
        logger.info(f"Модель сохранена в {model_path}")
    
    def load_model(self) -> None:
        models_config = self.config.get('models', {})
        model_path = models_config.get('model_path', 'models/stacking_model.pkl')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Файл модели не найден: {model_path}")
        
        model_data = joblib.load(model_path)
        self.model = model_data['model']
        self.feature_columns = model_data['feature_columns']
        logger.info(f"Модель загружена из {model_path}")
    
    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            logger.info("Модель не загружена, пробуем загрузить")
            self.load_model()
        
        missing_cols = set(self.feature_columns) - set(features.columns)
        if missing_cols:
            raise ValueError(f"Отсутствуют колонки: {missing_cols}")
        
        features = features[self.feature_columns]
        predictions = self.model.predict(features)
        logger.debug(f"Предсказание выполнено для {len(predictions)} объектов")
        
        return predictions
    
    def predict_from_file(self, forecast_path: Optional[str] = None) -> pd.DataFrame:
        if forecast_path is None:
            forecast_path = self.config.get('data', {}).get('forecast_path', 'data/forecast.csv')
        
        logger.info(f"Загрузка данных для прогноза из {forecast_path}")
        
        df = pd.read_csv(forecast_path, delimiter=';')
        metadata = df[['Well Name', 'Last']].copy()
        X_pred = df.drop(['Well Name', 'Last', 'BHP'], axis=1, errors='ignore')
        
        predictions = self.predict(X_pred)
        
        result = pd.DataFrame({
            'Well Name': metadata['Well Name'],
            'Date': pd.to_datetime(metadata['Last'], format='%d.%m.%y', errors='coerce'),
            'Predicted BHP': np.round(predictions, 1)
        })
        
        logger.info(f"Сформировано {len(result)} прогнозов")
        return result
