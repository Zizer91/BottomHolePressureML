# train.py
from src.pipeline import BHPPredictionPipeline

if __name__ == "__main__":
    pipeline = BHPPredictionPipeline("config.json")
    pipeline.train()
    
    results = pipeline.predict_from_file()
    print("\nПЕРВЫЕ 5 ПРОГНОЗОВ:")
    print(results.head())
    
    results.to_csv('predictions.csv', index=False)
    print("\nРезультаты сохранены в predictions.csv")