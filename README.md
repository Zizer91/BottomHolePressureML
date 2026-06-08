# BHP Prediction API

Микросервис для прогнозирования забойного давления (BHP) по параметрам скважины.

**Модель:** стекинг (RandomForest + GradientBoosting + DecisionTree + LinearRegression)  
**Качество:** R² = 0.9941, MSE = 67.59

---

## 📦 Быстрый старт

### Локальный запуск

```bash
git clone https://github.com/Zizer91/bhp-prediction.git
cd bhp-prediction
pip install -r requirements.txt
python train.py
uvicorn api.app:app --reload
```

#### Запуск через Docker
