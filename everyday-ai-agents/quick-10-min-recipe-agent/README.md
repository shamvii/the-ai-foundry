# Quick 10-Min Recipe Agent (Groq version)

A single-prompt Streamlit agent: give it what's in your kitchen and a hard
time budget, and it generates one realistic recipe that actually fits -
no recipes that quietly need 30 extra minutes of marinating.

Uses **Groq's free-tier API** (OpenAI-compatible client) instead of a paid
Anthropic key, so this runs at no cost.

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here
streamlit run app.py
```

Get a free key at [console.groq.com](https://console.groq.com) - no credit
card required.

## Deploy to Hugging Face Spaces

1. Create a new Space, SDK = Streamlit
2. Upload `app.py` and `requirements.txt`
3. In Space settings, add `GROQ_API_KEY` as a secret
4. Push - Spaces will build and run it automatically

## How it works

One `openai.OpenAI(base_url="https://api.groq.com/openai/v1")` call with a
system prompt that constrains the model to realistic timing and only the
ingredients provided. No retrieval, no agents, no external APIs - the whole
"agent" is a well-scoped prompt plus a form.

## Possible extensions

- Swap `MODEL` for a different Groq-hosted model if `openai/gpt-oss-120b` ever
  gets deprecated too (check console.groq.com/docs/models - Groq rotates its
  free-tier lineup fairly often, so treat any hardcoded model name as
  temporary)
- Swap the client for Anthropic/OpenAI/Gemini directly if you want to
  compare output quality across providers
- Add a "fridge photo" mode using a vision-capable model instead of typed
  ingredients
- Save generated recipes to a personal cookbook (Notion API or a simple
  local JSON store)
