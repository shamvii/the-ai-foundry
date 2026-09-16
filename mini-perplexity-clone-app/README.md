# Multi-Model Comparator (Perplexity like clone)

Ask a question, watch Claude, GPT, and Gemini answer it **live** (streamed token-by-token),
then Claude judges which two responses are most similar and which is most accurate.

## Local setup

```bash
pip install -r requirements.txt
mkdir .streamlit
cp secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml with your real API keys
streamlit run app.py
```

Keys needed:
- Anthropic: console.anthropic.com -> API Keys
- OpenAI: platform.openai.com -> API Keys
- Gemini: aistudio.google.com -> Get API key

## How it works

1. Your question is sent to all three models **concurrently** via background threads,
   each streaming its response into its own column as tokens arrive.
2. Once all three finish, the full texts are sent to Claude with labels A/B/C
   (randomized assignment, not "Claude/GPT/Gemini") so the judgment isn't biased
   by Claude recognizing its own writing style.
3. Claude judges via **tool use** — this forces a structured, guaranteed-valid
   response (which pair is most similar, which is most accurate, plus reasoning)
   instead of parsing free-text JSON.
4. The column-to-model mapping is revealed after judging, in an expander.

## Deploying (Streamlit Community Cloud — free)

1. Push this folder to a GitHub repo (do **not** commit `.streamlit/secrets.toml` —
   it's already excluded if you add `.streamlit/` to `.gitignore`).
2. Go to share.streamlit.io, sign in with GitHub, and point it at your repo/`app.py`.
3. In the app's **Settings -> Secrets**, paste the contents of `secrets.toml.example`
   with your real keys filled in.
4. Deploy. Every push to your main branch auto-redeploys.

## Notes / things to tune

- Model IDs (`CLAUDE_MODEL`, `GPT_MODEL`, `GEMINI_MODEL`) are set as constants near
  the top of `app.py` — swap `claude-sonnet-5` for `claude-haiku-4-5-20251001` if
  you want a cheaper judge call.
- Streaming three providers concurrently uses plain Python threads and a shared
  dict, polled every ~0.12s to repaint the Streamlit placeholders. This is simple
  and works well for 3 concurrent calls; it's not meant to scale to dozens.
- "Most accurate" is Claude's own opinion, not fact-checked ground truth — the app
  surfaces that caveat in the UI on purpose.
