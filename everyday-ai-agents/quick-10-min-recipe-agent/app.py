"""
Quick 10-Min Recipe Agent (Groq version)
------------------------------------------
Give it what's in your kitchen and how much time you have, and it
generates a recipe that actually fits the time budget - no "10 minute"
recipes that secretly need 40 minutes of marinating.

Uses Groq's free-tier API (OpenAI-compatible) instead of a paid Anthropic key.

Run locally:
    export GROQ_API_KEY=your_key_here
    streamlit run app.py

Deploy to Hugging Face Spaces:
    1. Create a new Space (SDK: Streamlit)
    2. Upload app.py and requirements.txt
    3. Add GROQ_API_KEY as a Space secret
"""

import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Quick Recipe Agent", page_icon="🍳", layout="centered")

MODEL = "openai/gpt-oss-120b"   # check console.groq.com/docs/models for current options

SYSTEM_PROMPT = """You are a practical home-cooking assistant. Given a list of
ingredients someone has on hand and a hard time budget, generate ONE realistic
recipe that can genuinely be made within that time, from start to plated food -
including any prep, cooking, and (if unavoidable) quick passive time like
boiling water. Do not suggest recipes that secretly need more time than given
(no "10 minutes active, 30 minutes marinating" tricks unless the person
explicitly has that time).

Rules:
- Only use ingredients the person listed, plus common pantry staples (salt,
  pepper, oil, water) unless they say they have more.
- If the time budget is too tight for a real meal, say so honestly and offer
  the closest realistic option instead of pretending it fits.
- Keep instructions short, numbered, and in an order a person can actually
  follow while cooking.
- Note near the top exactly how long each phase takes so the total is clear.

Format your response in clean markdown with these sections:
## [Recipe Name]
**Total time:** X minutes | **Serves:** N

### Ingredients
(bulleted list with quantities scaled to the servings requested)

### Steps
(numbered, with timing callouts like "(2 min)" where useful)

### Notes
(one or two short tips - substitutions, what to prep ahead, etc.)
"""


def generate_recipe(ingredients, minutes, servings, dietary_notes):
    client = OpenAI(
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
    )

    user_prompt = f"""Ingredients I have: {ingredients}
Time budget: {minutes} minutes
Servings needed: {servings}
Dietary notes / restrictions: {dietary_notes or "none"}

Generate one recipe that fits."""

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1200,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


# --- UI ---
st.title("🍳 Quick Recipe Agent")
st.caption("Tell it what's in your kitchen and how much time you've got.")

with st.form("recipe_form"):
    ingredients = st.text_area(
        "What ingredients do you have on hand?",
        placeholder="e.g. 2 eggs, half an onion, spinach, cheddar cheese, bread",
        height=100,
    )
    col1, col2 = st.columns(2)
    with col1:
        minutes = st.slider("Time budget (minutes)", min_value=5, max_value=45, value=10, step=5)
    with col2:
        servings = st.number_input("Servings", min_value=1, max_value=8, value=1)

    dietary_notes = st.text_input(
        "Any dietary notes? (optional)",
        placeholder="e.g. vegetarian, no dairy, low carb",
    )

    submitted = st.form_submit_button("Get me a recipe", type="primary")

if submitted:
    if not ingredients.strip():
        st.warning("Add at least a few ingredients first.")
    elif not os.environ.get("GROQ_API_KEY"):
        st.error("GROQ_API_KEY is not set. Add it as an environment variable or Space secret.")
    else:
        with st.spinner("Cooking up an idea..."):
            try:
                recipe = generate_recipe(ingredients, minutes, servings, dietary_notes)
                st.markdown(recipe)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

st.divider()
st.caption("Built as part of a personal AI-agent portfolio series.")
