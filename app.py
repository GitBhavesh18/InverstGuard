import streamlit as st
import pdfplumber
import tempfile
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


# -------- Configuration --------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or "Your_api_key"
MODEL_NAME = "deepseek/deepseek-chat-v3.1:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# -------- Utility Functions --------
def extract_pdf(file_bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        path = tmp.name
    try:
        with pdfplumber.open(path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    finally:
        try:
            os.remove(path)
        except:
            pass
    return text or ""

def build_prompt(product_type, goals, risk_profile, horizon, notes, content):
    content = content[:3000]  # Truncate to avoid long requests
    return f"""
You are an expert investment advisor for Indian users.
Product type: {product_type}
User goals: {goals}
Risk profile: {risk_profile}
Time horizon: {horizon}
Notes: {notes}

Here is the product document:
{content}

Analyze this product for alignment with goals, risks, charges, and red flags.
Return ONLY a JSON object with keys:
verdict, summary, pros, cons, charges_or_expenses, risks, red_flags, suitability, questions_to_ask.
"""

def call_openrouter(prompt):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful financial advisor."},
                {"role": "user", "content": prompt}
            ],
            extra_headers={
                "HTTP-Referer": "<YOUR_SITE_URL>",  # Optional
                "X-Title": "<YOUR_SITE_NAME>",      # Optional
            },
            extra_body={},
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API call failed: {e}")
        return None

def extract_json(text):
    try:
        return json.loads(text)
    except Exception:
        s = text.find("{")
        e = text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e+1])
            except:
                return None
    return None

# -------- Streamlit UI --------
st.set_page_config(page_title="InvestGuard", layout="wide")
st.title("InvestGuard – Investment & Insurance Advisor")

with st.form("input_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        product_type = st.selectbox("Product type", ["Health Insurance", "Mutual Fund", "Fixed Deposit", "Bond", "Other"])
        goals = st.text_area("User goals", value="Protect family health, reduce expenses.", height=100)
        notes = st.text_area("Notes / promises heard", value="Agent claims no co-pay.", height=80)
        text = st.text_area("Paste document text", value="", height=150)
    with col2:
        risk_profile = st.selectbox("Risk profile", ["Low", "Medium", "High"])
        horizon = st.selectbox("Time horizon", ["Short", "Medium", "Long"])
        file = st.file_uploader("Upload PDF", type=["pdf"])
    submit = st.form_submit_button("Analyze")

if submit:
    if not text.strip() and not file:
        st.error("Please upload a PDF or paste text to analyze.")
    else:
        with st.spinner("Analyzing..."):
            content = ""
            if file:
                content = extract_pdf(file.read())
            else:
                content = text.strip()

            prompt = build_prompt(product_type, goals, risk_profile, horizon, notes, content)
            output_text = call_openrouter(prompt)
            if output_text:
                parsed = extract_json(output_text)
                if not parsed:
                    st.error("Failed to parse the model response.")
                    st.code(output_text)
                else:
                    st.success(f"Verdict: {parsed.get('verdict','N/A')}")
                    st.subheader("Summary")
                    st.write(parsed.get("summary",""))
                    st.subheader("Pros")
                    for item in parsed.get("pros", []):
                        st.markdown(f"- {item}")
                    st.subheader("Cons")
                    for item in parsed.get("cons", []):
                        st.markdown(f"- {item}")
                    st.subheader("Charges / Expenses")
                    for item in parsed.get("charges_or_expenses", []):
                        st.markdown(f"- {item}")
                    st.subheader("Risks")
                    for item in parsed.get("risks", []):
                        st.markdown(f"- {item}")
                    st.subheader("Red Flags")
                    for item in parsed.get("red_flags", []):
                        st.markdown(f"- {item}")
                    st.subheader("Suitability")

                    # Robust handling for suitability being dict or string
                    suit = parsed.get("suitability", {})
                    if isinstance(suit, str):
                        parsed_suit = extract_json(suit)
                        if parsed_suit:
                            suit = parsed_suit

                    if isinstance(suit, dict):
                        st.write("Risk:", suit.get("risk", ""))
                        st.write("Horizon:", suit.get("horizon", ""))
                        st.write("Notes:", suit.get("notes", ""))
                    else:
                        st.write("Suitability:", suit)

                    st.subheader("Questions to Ask")
                    for item in parsed.get("questions_to_ask", []):
                        st.markdown(f"- {item}")
