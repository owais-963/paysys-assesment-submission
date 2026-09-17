# MiniPay Support Tool

An L2 support CLI for investigating individual MiniPay transactions,
built for Objective 4 (`requirements/04-python-support-tool.md`).

```bash
python support_tool.py --transaction TXN000123
```

- **`GUIDE.md`** — practical, example-driven usage guide: what each command
  does, what each anomaly means, what to do about it, with real output
  captured from a live run.
- **`USAGE.md`** — what each file/module does and why, plus a line-by-line
  mapping of every requirement in `requirements/04-python-support-tool.md`
  to where it's implemented.
- **`REPRODUCIBLE.md`** — placeholder-based Linux setup and run steps.

No credentials are hard-coded anywhere in the tool; configuration is
environment/`.env`-based (see `.env.example`), and `.env` itself is
git-ignored.
