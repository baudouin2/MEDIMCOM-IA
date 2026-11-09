# Plugging in a language model: the `CLE_API.txt` file

MEDIMCOM IA works **without any model**: the agents then follow their written, formally verified rules. A language model
makes the assistant more flexible: it rephrases, proposes questions and treatment options, and reads photos of documents.
To plug one in, **only one thing to do: paste an API key in `CLE_API.txt`**, at the root of the project.

## In 3 steps

1. **Get a key** from a provider (table below). Groq is free and fast: the simplest way to start.
2. **Open `CLE_API.txt`** (at the root of the folder; if it does not exist, it is created at first start). It contains a
   single line. Replace `votre_clé` with the key:
   ```
   CLE=votre_clé
   ```
3. **Start**: `bash lancer_local.sh` (or `python3 interface/serveur.py`). The terminal shows:
   ```
   ✓ CLE_API.txt: Groq (online) — free tier — model qwen/qwen3.8-27b
   ```
   The header of the doctor screen says it too: "Agents MEDIMCOM · modèle qwen/qwen3.8-27b (Groq · modèle open source)".

To change provider, just replace the key and start again: **the provider is recognised from the beginning of the key**.

## Recognised providers

| Key starts with | Provider | Price | Default model | Create the key |
|---|---|---|---|---|
| `gsk_` | Groq | **free** (quota per minute and per day) | `qwen/qwen3.8-27b` (open source) | https://console.groq.com/keys |
| `sk-or-` | OpenRouter | **free** for ":free" models | `google/gemma-4-31b-it:free` | https://openrouter.ai/keys |
| `AIza` | Google Gemini | **free** (quota per day) | `gemini-3.8-flash` | https://aistudio.google.com/apikey |
| (no prefix) | Mistral AI | **free** (Experiment plan) | `mistral-large-latest` | https://console.mistral.ai/api-keys |
| `xai-` | xAI (Grok) | paid (credits) | `grok-4.7` | https://console.x.ai |
| `sk-ant-` | Anthropic (Claude) | paid (credits) | `claude-haiku-5-5` | https://platform.claude.com/settings/keys |
| `sk-` / `sk-proj-` | OpenAI (GPT) | paid (credits) | `gpt-5.4-mini` | https://platform.openai.com/api-keys |

A Mistral key has no prefix: add the line `FOURNISSEUR=mistral`.

## The file: a single line

```
CLE=votre_clé
```

That is all that is needed. An empty key (or left as `votre_clé`): no online model, the agents follow their written rules.
The key can also be pasted alone, without `CLE=`.

**Optional lines**, to add only if needed, one per line under `CLE=`:

| Line | Role |
|---|---|
| `MODELE=…` | A model other than the recommended one (table above). Example: `MODELE=openai/gpt-oss-120b` (Groq), `MODELE=claude-sonnet-5-5`. If the model does not exist for the key, a close model of the same provider is taken and the terminal says so. |
| `CLE_SECOURS=…` | Key of **another** provider, used when the first one fails (quota reached, outage, no credits left). Example: free Groq as main, paid Grok as fallback. |
| `FOURNISSEUR=mistral` | Only for a Mistral key (it has no prefix). Other possible values: `groq`, `openrouter`, `gemini`, `xai`, `anthropic`, `openai`. |
| `PATIENTS_FICTIFS=non` | Switches the online model off (for example the day real patient data would be used). |

With an online model, messages go to the provider, outside the country: the terminal reminds it at start-up (fictitious
patients only, UAE Federal Law No. 2 of 2019, Art. 13).

## What is sent to the provider

By default the model only serves the **assistant**: it receives the (fictitious) record state, the agents' messages and, to
read a document, the photo or the text of the document. The **jurist stays deterministic**: its verdicts never depend on the
model. So that nothing leaves the computer: `bash lancer_local.sh ollama` (local open-source model, no key).

## Key security

- `CLE_API.txt` is **excluded from Git** (`.gitignore`): `git add .` does not take it, it never goes to GitHub. The
  repository only contains `CLE_API.exemple.txt`, without a key.
- The key is **never printed** (terminal, screen, journal, error messages): only the provider's name is.
- At start-up a copy is kept in `~/.config/medimcom/env` (readable by you only): if `CLE_API.txt` is emptied or the folder
  is replaced by a new version, this key is used again.
- A key, even a free one, is personal: whoever has it uses your quota or your credits. Share it only privately; if it has
  leaked, delete it at the provider and create another. Set a **spending limit** for a paid key.

## "Model unavailable"?

The doctor screen shows the cause in plain words next to "unavailable", and the assistant keeps working on written rules
(new attempt every 90 s). To check everything at once:

```bash
bash lancer_local.sh cle          # which provider and which model CLE_API.txt will give
bash lancer_local.sh diagnostic   # Internet, certificates, key, quota, model, real call: says what to do
```

| Message | Cause | What to do |
|---|---|---|
| key refused (HTTP 401/403) | wrong, deleted or badly copied key | copy the key again, without spaces |
| no credits / spending limit (HTTP 402/403) | paid account without credit | top up, or switch to a free key |
| quota reached (HTTP 429) | free limit per minute or per day | wait, or add `CLE_SECOURS=` |
| model retired or unknown | the provider renamed the model | `MODELE=` with a name listed by the diagnostic |
| Cloudflare firewall (error code: 1010) | network blocked by the provider | switch off the VPN or change network |
| address not found / timed out | no Internet or connection too slow | check the connection |
| CERTIFICATE_VERIFY_FAILED | HTTPS certificates missing (Python on macOS) | `pip install certifi` |
