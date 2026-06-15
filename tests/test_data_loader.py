import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.data_loader import (
    load_raw_data,
    remove_null_and_zero,
    remove_outliers_iqr,
    load_and_preprocess
)


@pytest.fixture
def sample_train_data(tmp_path):
    data = {
        'Well Name': ['W1', 'W2', 'W3'],
        'Last': ['01.01.2025', '02.01.2025', '03.01.2025'],
        'BHP': [100, 200, 300],
        'Choke': [10, 20, 30],
        'WHP': [50, 60, 70],
        'WHT': [40, 50, 60],
        'Gas': [1000, 2000, 3000],
        'Cond': [10, 20, 30],
        'Water': [5, 10, 15],
        'WOR': [0.05, 0.05, 0.05],
        'GOR': [100, 100, 100],
        'extra_col': [1, 2, 3]
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / 'teach_data.csv'
    df.to_csv(file_path, sep=';', index=False)
    return file_path


@pytest.fixture
def sample_forecast_data(tmp_path):
    data = {
        'Well Name': ['W4', 'W5'],
        'Last': ['04.01.2025', '05.01.2025'],
        'Choke': [15, 25],
        'WHP': [55, 65],
        'WHT': [45, 55],
        'Gas': [1500, 2500],
        'Cond': [15, 25],
        'Water': [8, 12],
        'WOR': [0.06, 0.06],
        'GOR': [110, 110],
        'BHP': [150, 250]
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / 'forecast_data.csv'
    df.to_csv(file_path, sep=';', index=False)
    return file_path


@pytest.fixture
def sample_data_with_outliers(tmp_path):
    data = {
        'BHP': [1, 2, 3, 4, 5, 100, 6, 7, 8, 9, 10],
        'Choke': [10] * 11,
        'WHP': [50] * 11
    }
    df = pd.DataFrame(data)
    file_path = tmp_path / 'outlier_data.csv'
    df.to_csv(file_path, sep=';', index=False)
    return file_path


class TestDataLoader:
    
    def test_load_raw_data(self, sample_train_data, sample_forecast_data):
        train_df, forecast_df = load_raw_data(
            str(sample_train_data),
            str(sample_forecast_data)
        )
        assert isinstance(train_df, pd.DataFrame)
        assert isinstance(forecast_df, pd.DataFrame)
        assert len(train_df) == 3
        assert len(forecast_df) == 2
    
    def test_remove_null_and_zero(self):
        data = {
            'Choke': [0, 10, 20, 0, 30],
            'BHP': [100, 200, 0, 400, 500],
            'extra': [1, np.nan, 3, 4, 5]
        }
        df = pd.DataFrame(data)
        df_clean = remove_null_and_zero(df)
        assert len(df_clean) == 1
        assert df_clean.iloc[0]['Choke'] == 10
        assert df_clean.iloc[0]['BHP'] == 200
    
    def test_remove_outliers_iqr(self, sample_data_with_outliers):
        df = pd.read_csv(sample_data_with_outliers, sep=';')
        original_len = len(df)
        df_clean = remove_outliers_iqr(df, column='BHP', multiplier=1.55)
        assert len(df_clean) == original_len - 1
        assert 100 not in df_clean['BHP'].values
    
    def test_load_and_preprocess(self, sample_train_data, sample_forecast_data):
        X_train, y_train, forecast_metadata = load_and_preprocess(
            str(sample_train_data),
            str(sample_forecast_data)
        )
        assert isinstance(X_train, pd.DataFrame)
        assert isinstance(y_train, pd.Series)
        assert isinstance(forecast_metadata, pd.DataFrame)
        assert 'extra_col' not in X_train.columns
        assert 'Well Name' in forecast_metadata.columns
        assert 'Last' in forecast_metadata.columns
        assert len(forecast_metadata) == 2
        assert not y_train.isna().any()
