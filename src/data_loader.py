"""
Модуль загрузки и предобработки данных для проекта прогнозирования BHP.
Содержит только функции, не содержит бизнес-логики обучения.
"""

import logging
import pandas as pd
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


def load_raw_data(train_path: str, forecast_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Загружает сырые данные из CSV-файлов."""
    logger.info(f"Загрузка обучающих данных из {train_path}")
    df_train = pd.read_csv(train_path, delimiter=';')
    
    logger.info(f"Загрузка данных для прогноза из {forecast_path}")
    df_forecast = pd.read_csv(forecast_path, delimiter=';')
    
    logger.info(f"Размер обучающей выборки: {df_train.shape}")
    logger.info(f"Размер выборки для прогноза: {df_forecast.shape}")
    
    return df_train, df_forecast


def extract_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Извлекает мета-информацию (Well Name, Last) из DataFrame."""
    well_col = 'Well Name' if 'Well Name' in df.columns else df.columns[0]
    date_col = 'Last' if 'Last' in df.columns else df.columns[1]
    
    metadata = df[[well_col, date_col]].copy()
    logger.debug(f"Извлечена мета-информация для {len(metadata)} записей")
    
    return metadata


def remove_meta_columns(df: pd.DataFrame, drop_target: bool = False) -> pd.DataFrame:
    """Удаляет мета-колонки (Well Name, Last, BHP)."""
    cols_to_drop = ['Well Name', 'Last']
    if drop_target and 'BHP' in df.columns:
        cols_to_drop.append('BHP')
    
    cols_to_drop_existing = [c for c in cols_to_drop if c in df.columns]
    
    if cols_to_drop_existing:
        df_result = df.drop(cols_to_drop_existing, axis=1)
        logger.debug(f"Удалены колонки: {cols_to_drop_existing}")
    else:
        df_result = df.copy()
    
    return df_result


def remove_null_and_zero(df: pd.DataFrame) -> pd.DataFrame:
    """Удаляет строки с пропусками (NaN) и нулевыми значениями в столбце 'Choke'."""
    before = len(df)
    
    df_clean = df.dropna()
    after_na = len(df_clean)
    
    if 'Choke' in df_clean.columns:
        df_clean = df_clean[df_clean['Choke'] != 0]
    
    if 'BHP' in df_clean.columns:
        df_clean = df_clean[df_clean['BHP'] != 0]
    
    after = len(df_clean)
    
    logger.info(f"Удалено строк: {before - after}")
    logger.info(f"  - из-за пропусков: {before - after_na}")
    logger.info(f"  - из-за нулевых значений: {after_na - after}")
    
    return df_clean


def remove_outliers_iqr(df: pd.DataFrame, column: str = 'BHP', multiplier: float = 1.55) -> pd.DataFrame:
    """Удаляет выбросы по методу IQR (межквартильного размаха)."""
    before = len(df)
    
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    
    df_clean = df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
    
    after = len(df_clean)
    logger.info(f"Удалено выбросов по {column}: {before - after}")
    
    return df_clean


def prepare_features_target(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Разделяет DataFrame на признаки (X) и целевую переменную (y = BHP)."""
    if 'BHP' not in df.columns:
        raise ValueError("DataFrame не содержит колонку 'BHP'")
    
    X = df.drop('BHP', axis=1)
    y = df['BHP'].copy()
    
    logger.info(f"Признаки (X): {X.shape}, целевая переменная (y): {y.shape}")
    
    return X, y


def load_and_preprocess(train_path: str, forecast_path: str) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Основная функция: загружает и предобрабатывает данные."""
    logger.info("=" * 40)
    logger.info("НАЧАЛО ЗАГРУЗКИ И ПРЕДОБРАБОТКИ ДАННЫХ")
    logger.info("=" * 40)
    
    df_train_raw, df_forecast_raw = load_raw_data(train_path, forecast_path)
    
    forecast_metadata = extract_metadata(df_forecast_raw)
    
    df_train_clean = remove_meta_columns(df_train_raw, drop_target=False)
    df_forecast_clean = remove_meta_columns(df_forecast_raw, drop_target=True)
    
    df_train_clean = remove_null_and_zero(df_train_clean)
    df_train_clean = remove_outliers_iqr(df_train_clean, column='BHP', multiplier=1.55)
    
    df_train_clean.reset_index(drop=True, inplace=True)
    forecast_metadata.reset_index(drop=True, inplace=True)
    
    X_train, y_train = prepare_features_target(df_train_clean)
    
    logger.info("=" * 40)
    logger.info(f"ГОТОВО: X_train={X_train.shape}, y_train={y_train.shape}")
    logger.info(f"        forecast_metadata={forecast_metadata.shape}")
    logger.info("=" * 40)
    
    return X_train, y_train, forecast_metadata
