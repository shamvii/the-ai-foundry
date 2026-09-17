"""
Skincare Routine Builder (OpenAI version)
-------------------------------------------
Builds a personalized AM/PM skincare routine based on skin type, concerns,
and budget. General cosmetic guidance only - not medical or dermatological
advice.

Uses the OpenAI API (Responses API) with GPT-5.6 Luna by default - it's
OpenAI's cheapest current tier and plenty capable for a structured
recommendation task like this.

Run locally:
    export OPENAI_API_KEY=your_key_here
    streamlit run app.py

Deploy to Hugging Face Spaces:
    1. Create a new Space (SDK: Streamlit)
    2. Upload app.py and requirements.txt
    3. Add OPENAI_API_KEY as a Space secret
"""

import os
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Skincare Routine Builder", page_icon="🧴", layout="centered")

# GPT-5.6 ships as three tiers: sol (flagship), terra (balanced), luna (cheapest).
# Luna is plenty for this task. Bump to "gpt-5.6-terra" if you want stronger
# reasoning on trickier ingredient-interaction questions.
MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = """You are a cosmetics-focused skincare routine assistant.
Build a simple, realistic AM/PM skincare routine based on the person's skin
type, stated concerns, budget, and any products they already own.

Rules:
- This is general cosmetic guidance only, not medical or dermatological
  advice. Do not diagnose skin conditions. If something sounds like it may
  need a dermatologist (persistent acne, unexplained rashes, suspicious
  moles, etc.), say so plainly and suggest seeing a professional, without
  trying to treat it yourself.
- Recommend product CATEGORIES first (e.g. "gentle gel cleanser", "niacinamide
  serum") and only name specific brands/products if the budget or request
  calls for concrete examples - keep brand suggestions to well-known,
  widely available options across a few price points, not a single pick.
- Keep the routine realistic: most people should not have more than
  4-5 steps per routine unless they specifically ask for more.
- Respect stated budget - do not recommend routines that clearly exceed it.
- Note which actives shouldn't be combined or should be introduced gradually
  (e.g. retinol + strong exfoliants).

Format your response in clean markdown:
## Your Routine

### AM
(numbered steps, each with product category + one-line purpose)

### PM
(numbered steps, each with product category + one-line purpose)

### Notes
- Any ingredients to introduce slowly or avoid combining
- One or two budget-friendly product examples per key step, if useful
- A brief, plain note on when to see a dermatologist instead of self-treating
"""


def generate_routine(skin_type, concerns, budget, current_products, notes):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_prompt = f"""Skin type: {skin_type}
Main concerns: {", ".join(concerns) if concerns else "none specified"}
Budget: {budget}
Products I already own/use: {current_products or "none listed"}
Additional notes: {notes or "none"}

Build my routine."""

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=user_prompt,
    )
    return response.output_text


# --- UI ---
st.title("🧴 Skincare Routine Builder")
st.caption("A quick AM/PM routine based on your skin type, concerns, and budget.")
st.info(
    "This gives general cosmetic guidance, not medical advice. "
    "See a dermatologist for persistent or concerning skin issues.",
    icon="ℹ️",
)

with st.form("skincare_form"):
    skin_type = st.selectbox(
        "Skin type",
        ["Oily", "Dry", "Combination", "Sensitive", "Normal", "Not sure"],
    )

    concerns = st.multiselect(
        "Main concerns (pick any that apply)",
        [
            "Acne / breakouts",
            "Anti-aging / fine lines",
            "Hyperpigmentation / dark spots",
            "Dryness / dehydration",
            "Redness / sensitivity",
            "Large pores",
            "Dullness",
            "Oiliness / shine",
        ],
    )

    budget = st.select_slider(
        "Budget per routine",
        options=["Minimal (drugstore only)", "Moderate", "No strict limit"],
        value="Moderate",
    )

    current_products = st.text_area(
        "Products you already use or own (optional)",
        placeholder="e.g. CeraVe cleanser, a vitamin C serum",
        height=80,
    )

    notes = st.text_input(
        "Anything else worth knowing? (optional)",
        placeholder="e.g. pregnant/breastfeeding, sensitive to fragrance",
    )

    submitted = st.form_submit_button("Build my routine", type="primary")

if submitted:
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY is not set. Add it as an environment variable or Space secret.")
    else:
        with st.spinner("Building your routine..."):
            try:
                routine = generate_routine(skin_type, concerns, budget, current_products, notes)
                st.markdown(routine)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

st.divider()
st.caption("Built as part of a personal AI-agent portfolio series.")
