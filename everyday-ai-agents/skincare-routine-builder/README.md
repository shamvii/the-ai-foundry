# Skincare Routine Builder

A single-prompt Streamlit agent that builds a personalized AM/PM skincare
routine from skin type, concerns, and budget. General cosmetic guidance
only - not medical or dermatological advice.

Uses the **OpenAI API** (Responses API) with `gpt-5.6-luna` by default -
OpenAI's cheapest current tier, which is plenty capable for a structured
recommendation task like this.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
streamlit run app.py
```

Get a key at [platform.openai.com](https://platform.openai.com/api-keys).
Note: unlike Groq, OpenAI's API is metered from the first request - check
current pricing at openai.com/api/pricing before running it a lot.

## Deploy to Hugging Face Spaces

1. Create a new Space, SDK = Streamlit
2. Upload `app.py` and `requirements.txt`
3. In Space settings, add `OPENAI_API_KEY` as a secret
4. Push - Spaces will build and run it automatically

## How it works

One `client.responses.create()` call with an `instructions` (system prompt)
that scopes the model to cosmetic (not medical) guidance, recommends
product categories before specific brands, and flags budget constraints.
No retrieval, no agents - the "intelligence" lives entirely in the prompt.

## Model tiers

GPT-5.6 ships as three tiers - pick based on how much reasoning you need:

| Model ID | Tier | Best for |
|---|---|---|
| `gpt-5.6-luna` | Cheapest, fastest | This kind of structured, well-defined task (default here) |
| `gpt-5.6-terra` | Balanced | If you want stronger reasoning on tricky ingredient interactions |
| `gpt-5.6-sol` | Flagship | Overkill for this agent, but available if needed |

Check developers.openai.com/api/docs/models for current pricing and
availability, since OpenAI updates its tier lineup fairly often.

## Possible extensions

- Add a "current product photo" mode using a vision-capable model to read
  ingredient lists off a bottle
- Track routine history over time and let the agent adjust as the season
  or skin changes
- Swap in Groq/Gemini/DeepSeek/Kimi for cost comparison (see the
  model-comparison notes in the project tracker)
