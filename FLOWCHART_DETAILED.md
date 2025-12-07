# Flowchart — Detailed Step-by-Step Technical Walkthrough

This document expands the simple flowchart into in-depth technical steps to help reviewers understand implementation, failure modes and testing considerations.

1. **Start / Bot initialization**
   - Load configuration from `.env` using `dotenv`.
   - Validate required environment variables (`OUTLOOK_USERNAME`, `OUTLOOK_APP_PASSWORD`).
   - Initialize logging and optional `TEST_MODE`.

2. **Connect to IMAP and Fetch UNSEEN**
   - Establish an IMAP SSL connection to `IMAP_HOST:IMAP_PORT`.
   - Select `INBOX` and search for `UNSEEN` messages.
   - For each message id returned, `FETCH (RFC822 FLAGS)` to retrieve the raw message.

3. **Parse message**
   - Use `email.policy.default` and `email.message_from_bytes` for robust parsing and charset handling.
   - Extract headers: `From`, `Subject`, `Message-ID`.
   - Prefer `text/plain` body; fall back to `text/html` with HTML strip for best-effort plain text.

4. **Auto-generated / Loop Detection**
   - Skip messages that have `Auto-Submitted` != `no`, or `Precedence` in (`bulk`, `list`, `auto_reply`).
   - Skip mailing-list messages (`List-Id`, `List-Unsubscribe`) and common bounce addresses (`mailer-daemon`, `postmaster`).

5. **Extract 'Business email'**
   - Search for the phrase `Business email` (case-insensitive) with flexible separators (`:`, `-`, whitespace).
   - Validate the extracted token with a strict regex to ensure it's a proper email address.
   - Also support finding the address on the next line if the phrase is on its own line.

6. **Prepare and send reply**
   - Compose a professional subject prefix and body (templates included).
   - Set `In-Reply-To` header to the original `Message-ID` for proper threading.
   - Respect `TEST_MODE` to avoid sending real email during development.
   - Use `smtplib.SMTP_SSL` and login using credentials from environment.

7. **Flagging and persistence**
   - On successful send: mark the original message with `\Answered \Seen`.
   - On send failure: mark `\Seen` to avoid immediate reprocessing; optionally add retry/backoff logic.
   - Optional: persist a small SQLite DB of `Message-ID`s that were replied to, to prevent duplicate replies across restarts.

8. **Operational concerns & monitoring**
   - Add rotating logs and a monitoring/alerting integration for repeated SMTP failures.
   - Consider switching polling to `IMAP IDLE` for real-time behavior.
   - Rate-limit or batch replies for large influxes.
   - Ensure credentials are stored in secret stores (Vault, GitHub secrets) for production.

9. **Testing**
   - Unit-test `extract_business_email` with multiple email body fixtures (plain, HTML, different separators).
   - Integration test with a test mail account and `TEST_MODE` off for final validation.

This document maps directly to `improved_auto_reply.py` and the included tests to make reviewer verification straightforward.
