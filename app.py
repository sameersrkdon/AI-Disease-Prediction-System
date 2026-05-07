from datetime import datetime
import json
import os
import pickle
import sqlite3

import numpy as np
from flask import Flask, render_template, request

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "predictions.db")

cancer_model = pickle.load(open("models/cancer_model.pkl", "rb"))
diabetes_model = pickle.load(open("models/diabetes_model.pkl", "rb"))
heart_model = pickle.load(open("models/heart_model.pkl", "rb"))

FIELDS = {
    "heart": [
        ("thalach", "Max Heart Rate", 60, 220),
        ("cp", "Chest Pain Type", 0, 3),
        ("ca", "Major Vessels", 0, 3),
        ("thal", "Thalassemia", 1, 3),
        ("oldpeak", "ST Depression", 0, 7),
        ("age", "Age", 1, 120),
        ("chol", "Cholesterol", 80, 600),
        ("trestbps", "Resting BP", 70, 250),
    ],
    "cancer": [
        ("concave_points_worst", "Worst Concave Points", 0, 1),
        ("perimeter_worst", "Worst Perimeter", 1, 300),
        ("concave_points_mean", "Mean Concave Points", 0, 1),
        ("radius_worst", "Worst Radius", 1, 50),
        ("perimeter_mean", "Mean Perimeter", 1, 250),
        ("area_worst", "Worst Area", 1, 5000),
        ("radius_mean", "Mean Radius", 1, 40),
        ("area_mean", "Mean Area", 1, 3000),
    ],
    "diabetes": [
        ("Pregnancies", "Pregnancies", 0, 20),
        ("Glucose", "Glucose", 0, 300),
        ("BloodPressure", "Blood Pressure", 0, 200),
        ("SkinThickness", "Skin Thickness", 0, 100),
        ("Insulin", "Insulin", 0, 900),
        ("BMI", "BMI", 0, 80),
        ("DiabetesPedigreeFunction", "Diabetes Pedigree Function", 0, 3),
        ("Age", "Age", 1, 120),
    ],
}


def init_db():
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_name TEXT NOT NULL,
                result TEXT NOT NULL,
                probability INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                input_values TEXT NOT NULL,
                top_factors TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def validate_features(condition_name):
    features = []
    clean_values = {}
    errors = []
    for field, label, min_value, max_value in FIELDS[condition_name]:
        raw_value = request.form.get(field, "").strip()
        try:
            value = float(raw_value)
        except ValueError:
            errors.append(f"{label} must be a number.")
            continue
        if value < min_value or value > max_value:
            errors.append(f"{label} must be between {min_value} and {max_value}.")
        features.append(value)
        clean_values[label] = raw_value
    return features, clean_values, errors


def positive_probability(model, data):
    if not hasattr(model, "predict_proba"):
        return None
    probabilities = model.predict_proba(data)[0]
    classes = list(getattr(model, "classes_", []))
    positive_index = classes.index(1) if 1 in classes else len(probabilities) - 1
    return round(float(probabilities[positive_index]) * 100)


def risk_level(probability, positive):
    if probability is None:
        return "HIGH RISK" if positive else "LOW RISK"
    if probability >= 65:
        return "HIGH RISK"
    if probability >= 35:
        return "MEDIUM RISK"
    return "LOW RISK"


def top_factors(model, condition_name):
    importances = getattr(model, "feature_importances_", None)
    labels = [label for _, label, _, _ in FIELDS[condition_name]]
    if importances is None:
        return [{"name": label, "importance": 0} for label in labels[:4]]
    ranked = sorted(zip(labels, importances), key=lambda item: item[1], reverse=True)[:4]
    total = sum(value for _, value in ranked) or 1
    return [{"name": name, "importance": round((value / total) * 100)} for name, value in ranked]


def save_prediction(condition_name, result, probability, confidence, level, values, factors):
    created_at = datetime.now().strftime("%d %b %Y, %I:%M %p")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO predictions
            (condition_name, result, probability, confidence, risk_level, input_values, top_factors, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                condition_name,
                result,
                probability,
                confidence,
                level,
                json.dumps(values),
                json.dumps(factors),
                created_at,
            ),
        )
        return cursor.lastrowid, created_at


def run_prediction(condition_name, model, positive_label, negative_label, template_name):
    features, values, errors = validate_features(condition_name)
    if errors:
        return render_template(
            template_name.replace("-result", ""),
            errors=errors,
            previous_values=request.form,
        )

    data = np.array(features, dtype=float).reshape(1, -1)
    prediction = model.predict(data)[0]
    is_positive = int(prediction) == 1
    result = positive_label if is_positive else negative_label
    probability = positive_probability(model, data)
    if probability is None:
        probability = 100 if is_positive else 0
    confidence = max(probability, 100 - probability)
    level = risk_level(probability, is_positive)
    factors = top_factors(model, condition_name)
    prediction_id, created_at = save_prediction(condition_name, result, probability, confidence, level, values, factors)

    return render_template(
        template_name,
        prediction_id=prediction_id,
        prediction_text=result,
        probability=probability,
        confidence=confidence,
        risk_level=level,
        values=values,
        top_factors=factors,
        created_at=created_at,
    )


def get_prediction(prediction_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["input_values"] = json.loads(item["input_values"])
    item["top_factors"] = json.loads(item["top_factors"])
    return item


init_db()


@app.route("/")
def login():
    return render_template("login.html")


@app.route("/index")
def home():
    return render_template("index.html")


@app.route("/history")
def history():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM predictions ORDER BY id DESC LIMIT 20").fetchall()
    return render_template("patient-history.html", predictions=rows)


@app.route("/report/<int:prediction_id>")
def report(prediction_id):
    prediction = get_prediction(prediction_id)
    return render_template("report.html", prediction=prediction)


@app.route("/heart")
def heart():
    return render_template("heart.html")


@app.route("/predict_heart", methods=["POST"])
def predict_heart():
    return run_prediction("heart", heart_model, "Positive", "Negative", "heart-result.html")


@app.route("/cancer")
def cancer():
    return render_template("breast-cancer.html")


@app.route("/predict_cancer", methods=["POST"])
def predict_cancer():
    return run_prediction("cancer", cancer_model, "Malignant", "Benign", "breast-result.html")


@app.route("/diabetes")
def diabetes():
    return render_template("diabetes.html")


@app.route("/predict_diabetes", methods=["POST"])
def predict_diabetes():
    return run_prediction("diabetes", diabetes_model, "Diabetic", "Non-Diabetic", "diabetes-result.html")


if __name__ == "__main__":
    app.run(debug=True)
