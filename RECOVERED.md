# Recovered source

Reconstructed from the OpenHands conversation `a53b2a11-cb93-4cf9-ac6b-770d75eb4f77`
("Create a new bot ..."), whose sandbox was lost. The files reflect the working-tree
state at the last recorded edit.

Notes:
- `.env` is intentionally NOT included: it held live credentials (bot token, database
  URI). Use `.env.example` as a template and fill in your own values.
- `config.py` contains hardcoded fallback credentials; consider rotating/removing them.
- This tree was syntax-checked (`python3 -m py_compile`) but not run in the recovery
  environment (runtime deps such as pyrogram/libtorrent are not installed here).
