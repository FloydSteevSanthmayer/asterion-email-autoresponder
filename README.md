# Asterion Email Autoresponder

![Flowchart](flowchart_colored.png)

**Asterion Email Autoresponder** is a production-oriented Python service that provides reliable, automated acknowledgements for incoming business enquiries. It parses message bodies to locate the declared contact address, validates and sanitizes the extracted address, and sends threaded, professional responses while avoiding reply loops. The project is designed to be easy to deploy, test, and monitor in small-to-medium business environments.

---

## Key Features

- **Reliable IMAP/SMTP integration:** Secure connections using IMAP over SSL and SMTP over SSL.
- **Robust message parsing:** Charset-aware handling, preferred `text/plain` extraction with `text/html` fallback and sanitization.
- **Loop prevention:** Skips auto-generated messages (`Auto-Submitted`, `Precedence`) and common bounce/list senders.
- **Threaded replies:** Replies include `In-Reply-To` where available to preserve conversation threading.
- **Safe testing mode:** `TEST_MODE` allows validation without sending real email.
- **Configurable templates:** Professional subject and body templates with company/sender variables.
- **Container-ready & CI-friendly:** Dockerfile, GitHub Actions CI, Dependabot and pre-commit configuration included.
- **Automated tests:** Pytest scaffold with focused unit tests for parsing logic.

---

## Repository contents (selected)

- `improved_auto_reply.py` — Core service (IMAP fetch → parse → SMTP reply).  
- `flowchart_colored.mmd` — Mermaid source for the flowchart.  
- `flowchart_colored.png` — Rendered flowchart image (included).  
- `app.py` — Minimal Streamlit launcher for quick inspection.  
- `Dockerfile` — Container recipe for production deployment.  
- `.github/workflows/ci.yml` — Basic CI that installs deps and runs tests.  
- `tests/` — Pytest tests, including parsing edge cases.  
- `CONTRIBUTING.md`, `LICENSE`, `.env.example`, `.pre-commit-config.yaml`

---

## Architecture & Design Notes

The service follows a simple poll-and-process architecture (polling interval configurable via `POLL_INTERVAL_SECONDS`), with the following high-level stages:

1. **Fetch** unread messages (`UNSEEN`) from `INBOX` using IMAP over SSL.  
2. **Parse** message headers and body using `email.policy.default` to ensure correct charset handling.  
3. **Detect** `Business email` lines and extract the declared contact address; validate against a strict regex.  
4. **Filter** messages that are auto-generated, list-sent, or obvious bounce notifications.  
5. **Reply** using SMTP over SSL; include `In-Reply-To` for thread continuity.  
6. **Flag** the original message (`\Answered`, `\Seen`) to avoid duplicate replies.

Operational considerations documented include IMAP IDLE vs polling, persistent deduplication (SQLite), rate-limiting, and monitoring recommendations.

---

## Quickstart (developer)

1. Clone the repository:
```bash
git clone <repo-url>
cd asterion-email-autoresponder
```

2. Copy environment example and set credentials:
```bash
cp .env.example .env
# Edit .env with your values: OUTLOOK_USERNAME, OUTLOOK_APP_PASSWORD, IMAP_HOST, SMTP_HOST, etc.
```

3. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

4. Run in test mode (recommended):
```bash
# Ensure TEST_MODE=true in .env to avoid sending real emails
python improved_auto_reply.py
```

5. Optional: preview flowchart with Streamlit
```bash
streamlit run app.py
```

---

## Docker

Build and run a containerized instance:
```bash
docker build -t asterion-email-autoresponder .
docker run --env-file .env asterion-email-autoresponder
```

---

## CI / Testing

- CI runs `pytest` for the test matrix defined in `.github/workflows/ci.yml`.  
- Pre-commit hooks (Black, isort, Flake8) are preconfigured via `.pre-commit-config.yaml`.

Run tests locally:
```bash
pytest -q
```

---

## Security & Production Guidance

- **Credentials**: Use environment variables or a secrets manager. Never commit `.env` to source control.  
- **App passwords / OAuth**: Prefer app-specific passwords or OAuth where possible.  
- **Rate limiting**: Implement throttling for high-volume mailboxes.  
- **Persistence**: For at-least-once delivery semantics use a persistent store to track replied `Message-ID`s.  
- **Monitoring**: Collect logs, and add alerting for repeated failures.

---

## Contributing

See `CONTRIBUTING.md` for the contribution workflow, testing guidelines, and code style conventions. Short summary: fork → branch → tests → PR.

---

## License

This project is released under the MIT License. See `LICENSE` for details.

---

**Author**: Floyd Steev Santhmayer — Asterion Email Autoresponder
