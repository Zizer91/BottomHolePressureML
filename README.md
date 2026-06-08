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

### Запуск через Docker
```
docker-compose up --build
```
API будет доступен: http://localhost:8000

### 📡 API Endpoints
|Метод | Эндпоинт | Описание |
|-------------|-------------|-------------|
| GET    | /health    | Проверка статуса сервиса    |
| GET    | /docs    | Swagger документация    |
| POST    | /predict	    | Прогноз для одной скважины    |
| POST    | /predict_batch		    | Прогноз для нескольких скважин    |

### 📤 Пример запроса
```
curl -X POST "http://localhost:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "choke": 42.5,
    "whp": 280.0,
    "wht": 65.0,
    "gas": 150.0,
    "cond": 30.0,
    "water": 5.0,
    "wor": 0.1,
    "gor": 500.0
  }'
```
### 📤 Пример запроса
```
{
  "bhp": 374.2,
  "status": "success"
}
```
### 👤 Автор
Павел — инженер по разработке месторождений, 11+ лет опыта, экспертиза в ML и автоматизации.
GitHub: Zizer91
Email: tsitsero@gmail.com
