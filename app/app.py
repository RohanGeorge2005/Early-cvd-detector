"""Educational Streamlit interface for portable ten-year CHD risk inference."""

import json
import math
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="CVD Risk Estimate",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "cvd_model_portable.json"
EXPECTED_FEATURES = [
    "male", "age", "education", "currentSmoker", "cigsPerDay", "BPMeds",
    "prevalentStroke", "prevalentHyp", "diabetes", "totChol", "sysBP",
    "diaBP", "BMI", "heartRate", "glucose",
]


@st.cache_data(show_spinner="Loading risk model...")
def load_model(path: Path, version: int) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


if not MODEL_PATH.exists():
    st.error("Risk model file is missing. Run cvd_prediction.ipynb to create cvd_model_portable.json.")
    st.stop()

model = load_model(MODEL_PATH, MODEL_PATH.stat().st_mtime_ns)
if model.get("format") != "portable_logistic_regression_v1" or model.get("feature_names") != EXPECTED_FEATURES:
    st.error("The risk model file is invalid or does not match the app input fields.")
    st.stop()


def predict_probability(values: list[float]) -> float:
    """Apply exported imputation, scaling, and logistic-regression parameters."""
    filled = [
        float(statistic if value is None else value)
        for value, statistic in zip(values, model["imputer_statistics"])
    ]
    transformed = filled + [0.0] * (len(model["scaler_mean"]) - len(filled))
    scaled = [
        (value - mean) / scale
        for value, mean, scale in zip(transformed, model["scaler_mean"], model["scaler_scale"])
    ]
    logit = model["intercept"] + sum(weight * value for weight, value in zip(model["coefficients"], scaled))
    return 1.0 / (1.0 + math.exp(-max(min(logit, 700.0), -700.0)))


st.markdown(
    """
    <style>
        :root { --ink: #132238; --muted: #607089; --primary: #2563eb; --border: #dce5f0; }
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { max-width: 1120px; padding-top: 2.25rem; padding-bottom: 3rem; }
        .hero { background: linear-gradient(115deg, #102a43 0%, #1d4ed8 100%); color: #fff;
                padding: 2.35rem; border-radius: 20px; margin-bottom: 1.5rem;
                box-shadow: 0 16px 36px rgba(29, 78, 216, .20); }
        .hero h1 { font-size: 2rem; margin: 0 0 .45rem; font-weight: 700; letter-spacing: -.02em; }
        .hero p { margin: 0; color: #dbeafe; font-size: 1rem; }
        .eyebrow { color: #93c5fd; font-weight: 700; letter-spacing: .08em; font-size: .72rem; text-transform: uppercase; }
        .section-title { color: #e2e8f0; font-weight: 700; font-size: 1.05rem; margin: 1.25rem 0 .55rem; }
        div[data-testid="stForm"] { border: 1px solid var(--border); border-radius: 18px; padding: 1.2rem 1.4rem .5rem; background: #fff; }
        div[data-testid="stForm"] .section-title,
        div[data-testid="stForm"] label,
        div[data-testid="stForm"] p { color: #132238 !important; }
        div[data-testid="stFormSubmitButton"] button { background: #2563eb; border: 0; border-radius: 10px;
            color: #fff; font-weight: 700; min-height: 2.8rem; }
        div[data-testid="stFormSubmitButton"] button:hover { background: #1d4ed8; }
        div[data-testid="stMetric"] { padding: .8rem; border-radius: 12px; background: #172033; border: 1px solid #334155; }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f8fafc !important; }
        [data-testid="stSidebar"] { border-right: 1px solid var(--border); }
        [data-testid="stSidebar"] .stMarkdown { color: var(--ink); }
    </style>
    <div class="hero">
        <div class="eyebrow">Clinical decision support demo</div>
        <h1>Cardiovascular risk estimate</h1>
        <p>Enter a patient profile to generate an educational ten-year coronary heart disease probability estimate.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Model summary")
    st.write(model["model_name"])
    st.caption("Portable deployment model. It does not require scikit-learn or XGBoost at runtime.")
    st.markdown("---")
    st.markdown("### Important notice")
    st.caption("Educational use only. This estimate is not a diagnosis, treatment recommendation, or medical device output.")

with st.form("cvd_form"):
    st.markdown('<div class="section-title">Demographics</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        gender = st.selectbox("Gender", ["Male", "Female"])
    with c2:
        age = st.number_input("Age", min_value=18, max_value=100, value=40)
    with c3:
        education = st.selectbox("Education level", [1, 2, 3, 4], index=1)

    st.markdown('<div class="section-title">Lifestyle</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        current_smoker = st.selectbox("Current smoker", ["No", "Yes"])
    with c2:
        cigs_per_day = st.number_input("Cigarettes per day", min_value=0, max_value=100, value=0)

    st.markdown('<div class="section-title">Medical history</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        bp_meds = st.selectbox("BP medication", ["No", "Yes"])
    with c2:
        prevalent_stroke = st.selectbox("Previous stroke", ["No", "Yes"])
    with c3:
        prevalent_hyp = st.selectbox("Hypertension", ["No", "Yes"])
    with c4:
        diabetes = st.selectbox("Diabetes", ["No", "Yes"])

    st.markdown('<div class="section-title">Vitals and labs</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        tot_chol = st.number_input("Total cholesterol, mg/dL", 100.0, 500.0, 200.0)
    with c2:
        sys_bp = st.number_input("Systolic BP, mmHg", 70.0, 250.0, 120.0)
    with c3:
        dia_bp = st.number_input("Diastolic BP, mmHg", 40.0, 150.0, 80.0)
    c1, c2, c3 = st.columns(3)
    with c1:
        bmi = st.number_input("BMI", 10.0, 60.0, 25.0)
    with c2:
        heart_rate = st.number_input("Heart rate, bpm", 40.0, 200.0, 75.0)
    with c3:
        glucose = st.number_input("Glucose, mg/dL", 40.0, 400.0, 80.0)

    submitted = st.form_submit_button("Calculate risk estimate", use_container_width=True)

if submitted:
    if current_smoker == "No" and cigs_per_day > 0:
        cigs_per_day = 0
        st.info("Cigarettes per day was reset to zero because current smoker is set to no.")

    values = [
        int(gender == "Male"), age, education, int(current_smoker == "Yes"), cigs_per_day,
        int(bp_meds == "Yes"), int(prevalent_stroke == "Yes"), int(prevalent_hyp == "Yes"),
        int(diabetes == "Yes"), tot_chol, sys_bp, dia_bp, bmi, heart_rate, glucose,
    ]
    probability = predict_probability(values)

    st.markdown('<div class="section-title">Risk estimate</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Estimated ten-year CHD probability", f"{probability:.1%}")
    with c2:
        st.progress(probability)
        if probability < 0.2:
            st.success("Lower model-estimated risk")
        elif probability < 0.5:
            st.warning("Moderate model-estimated risk")
        else:
            st.error("Higher model-estimated risk")

    st.caption("Interpret this estimate with a qualified healthcare professional and the full clinical context.")
