from src.pipeline import BHPPredictionPipeline

if __name__ == "__main__":
    pipeline = BHPPredictionPipeline("config.json")
    pipeline.train()
    results = pipeline.predict_from_file()
    print(results.head())
