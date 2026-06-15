"""
Точка входа для обучения модели.
"""

import logging
from src.pipeline import BHPPredictionPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    pipeline = BHPPredictionPipeline("config.json")
    pipeline.train()
    
    results = pipeline.predict_from_file()
    print("\nПЕРВЫЕ 5 ПРОГНОЗОВ:")
    print(results.head())
    
    results.to_csv('predictions.csv', index=False)
    print("\nРезультаты сохранены в predictions.csv")
