"""
Модуль обучения моделей для прогнозирования BHP.
"""

import logging
import numpy as np
import pandas as pd
from typing import Tuple, List

from sklearn.model_selection import train_test_split, KFold
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

logger = logging.getLogger(__name__)


class StackingModel:
    """Обёртка для модели стекинга."""
    
    def __init__(self, base_models: List[Tuple[str, object]], meta_model: object):
        self.base_models = base_models
        self.meta_model = meta_model
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        base_preds = np.column_stack([
            model.predict(X) for _, model in self.base_models
        ])
        return self.meta_model.predict(base_preds)


def get_base_models(random_state: int = 42) -> List[Tuple[str, object]]:
    """Возвращает список базовых моделей."""
    models = [
        ('RandomForest', RandomForestRegressor(n_estimators=42, random_state=random_state)),
        ('GradientBoosting', GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=3, random_state=random_state)),
        ('DecisionTree', DecisionTreeRegressor(random_state=random_state))
    ]
    logger.info(f"Создано {len(models)} базовых моделей: {[m[0] for m in models]}")
    return models


def create_meta_features(X_train: pd.DataFrame, y_train: pd.Series,
                         base_models: List[Tuple[str, object]], 
                         n_splits: int = 5, 
                         random_state: int = 42) -> np.ndarray:
    """Создаёт мета-признаки для стекинга через кросс-валидацию."""
    logger.info(f"Создание мета-признаков через {n_splits}-fold кросс-валидацию")
    
    n_samples = X_train.shape[0]
    n_models = len(base_models)
    meta_features = np.zeros((n_samples, n_models))
    
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    for model_idx, (name, model) in enumerate(base_models):
        logger.info(f"Обработка модели {name} ({model_idx+1}/{n_models})")
        
        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X_train)):
            X_tr_fold = X_train.iloc[train_idx]
            y_tr_fold = y_train.iloc[train_idx]
            X_val_fold = X_train.iloc[val_idx]
            
            model_copy = model.__class__(**model.get_params())
            model_copy.fit(X_tr_fold, y_tr_fold)
            meta_features[val_idx, model_idx] = model_copy.predict(X_val_fold)
    
    logger.info(f"Мета-признаки созданы: форма {meta_features.shape}")
    return meta_features


def train_meta_model(meta_features: np.ndarray, y_train: pd.Series) -> LinearRegression:
    """Обучает мета-модель (линейную регрессию) на мета-признаках."""
    logger.info("Обучение мета-модели (LinearRegression)")
    meta_model = LinearRegression()
    meta_model.fit(meta_features, y_train)
    
    meta_pred = meta_model.predict(meta_features)
    meta_r2 = r2_score(y_train, meta_pred)
    logger.info(f"Мета-модель обучена. R2 на обучающих мета-признаках: {meta_r2:.4f}")
    
    return meta_model


def train_stacking_model(X_train: pd.DataFrame, 
                         y_train: pd.Series,
                         test_size: float = 0.25,
                         random_state: int = 42,
                         n_splits: int = 5) -> StackingModel:
    """Обучает полную модель стекинга."""
    logger.info("=" * 50)
    logger.info("НАЧАЛО ОБУЧЕНИЯ МОДЕЛИ СТЕКИНГА")
    logger.info("=" * 50)
    
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=test_size, random_state=random_state
    )
    logger.info(f"Разделение данных: train={X_tr.shape}, val={X_val.shape}")
    
    base_models = get_base_models(random_state)
    
    meta_features_tr = create_meta_features(X_tr, y_tr, base_models, n_splits, random_state)
    
    meta_model = train_meta_model(meta_features_tr, y_tr)
    
    trained_base_models = []
    for name, model in base_models:
        logger.info(f"Финальное обучение {name} на всех данных")
        model.fit(X_tr, y_tr)
        trained_base_models.append((name, model))
    
    base_preds_val = np.column_stack([model.predict(X_val) for _, model in trained_base_models])
    final_pred_val = meta_model.predict(base_preds_val)
    
    mse = mean_squared_error(y_val, final_pred_val)
    r2 = r2_score(y_val, final_pred_val)
    
    logger.info("=" * 40)
    logger.info(f"КАЧЕСТВО МОДЕЛИ НА ВАЛИДАЦИИ:")
    logger.info(f"  MSE: {mse:.2f}")
    logger.info(f"  R²:  {r2:.4f}")
    logger.info("=" * 40)
    
    stacking_model = StackingModel(trained_base_models, meta_model)
    logger.info("Модель стекинга успешно создана")
    return stacking_model
