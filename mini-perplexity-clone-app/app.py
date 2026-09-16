import random

import anthropic
import openai
import streamlit as st
from google import genai

st.set_page_config(page_title="Multi-Model Comparator", layout="wide")
st.title("🔍 Multi-Model Comparator")
st.caption(
    "Ask one question. Watch Claude, GPT, and Gemini answer live, "
    "then let Claude judge which two responses agree most and which seems most accurate."
)

question = st.text_input("Enter your question")
go = st.button("Compare", type="primary")


# ---------- Streaming functions (each is a generator yielding text chunks) ----------

def stream_claude(prompt: str, model: str = "claude-sonnet-4-6"):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    with client.messages.stream(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_gpt(prompt: str, model: str = "gpt-4o"):
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_gemini(prompt: str, model: str = "gemini-3.6-flash"):
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    for chunk in client.models.generate_content_stream(model=model, contents=prompt):
        if chunk.text:
            yield chunk.text


MODEL_STREAMS = {
    "Claude": stream_claude,
    "GPT": stream_gpt,
    "Gemini": stream_gemini,
}


# ---------- Judge step (Claude, using tool use for guaranteed structured output) ----------

def get_verdict(question: str, responses: dict) -> dict:
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    tools = [
        {
            "name": "submit_verdict",
            "description": "Submit the comparison verdict between three AI responses",
            "input_schema": {
                "type": "object",
                "properties": {
                    "most_similar_pair": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["A", "B", "C"]},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "similarity_reasoning": {"type": "string"},
                    "most_accurate": {"type": "string", "enum": ["A", "B", "C"]},
                    "accuracy_reasoning": {"type": "string"},
                },
                "required": [
                    "most_similar_pair",
                    "similarity_reasoning",
                    "most_accurate",
                    "accuracy_reasoning",
                ],
            },
        }
    ]

    prompt = f"""Question asked: {question}

Response A: {responses['A']}

Response B: {responses['B']}

Response C: {responses['C']}

Compare these three responses. Identify which two are most similar in content \
and approach, and separately judge which single response seems most accurate \
based on your own knowledge. The labels A/B/C are randomized and don't correspond \
to any particular model — judge the content on its own merits."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        tools=tools,
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].input


# ---------- Main flow ----------

if go and not question:
    st.warning("Enter a question first.")

elif go and question:
    # Randomize which model gets which label so Claude can't just favor its own style
    order = list(MODEL_STREAMS.items())
    random.shuffle(order)
    labels = ["A", "B", "C"]
    label_map = {}  # label -> real model name, revealed after judging
    responses = {}

    cols = st.columns(3)
    for col, label, (model_name, stream_fn) in zip(cols, labels, order):
        label_map[label] = model_name
        with col:
            st.subheader(f"Response {label}")
            try:
                responses[label] = st.write_stream(stream_fn(question))
            except Exception as e:
                st.error(f"Failed: {e}")
                responses[label] = ""

    st.divider()
    st.subheader("⚖️ Claude's verdict")

    if all(responses.values()):
        with st.spinner("Judging..."):
            try:
                verdict = get_verdict(question, responses)
            except Exception as e:
                st.error(f"Judging failed: {e}")
                verdict = None

        if verdict:
            pair = verdict["most_similar_pair"]
            st.markdown(f"**Most similar pair:** {pair[0]} & {pair[1]}")
            st.write(verdict["similarity_reasoning"])
            st.markdown(f"**Most accurate:** {verdict['most_accurate']}")
            st.write(verdict["accuracy_reasoning"])

            with st.expander("Reveal which model was which"):
                for label, name in label_map.items():
                    st.write(f"**{label}** → {name}")
    else:
        st.warning("One or more models failed to respond — skipping the judge step.")
