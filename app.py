import imaplib
import email
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
import smtplib
import ssl
import re
import time
import os
from dotenv import load_dotenv
import logging
from socket import gaierror

load_dotenv()

# Config
IMAP_HOST = os.getenv("IMAP_HOST", "mail.asterionsolutions.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
SMTP_HOST = os.getenv("SMTP_HOST", "mail.asterionsolutions.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
USERNAME = os.getenv("OUTLOOK_USERNAME")
PASSWORD = os.getenv("OUTLOOK_APP_PASSWORD")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 120))
TEST_MODE = os.getenv("TEST_MODE", "false").lower() in ("1", "true", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Professionalized template values (updated per your request)
COMPANY_NAME = "Asterion Solutions Pvt. Ltd."   # dummy company name
SENDER_NAME = "Priya Sharma"                    

REPLY_SUBJECT_PREFIX = "Acknowledgement: "
REPLY_BODY_TEMPLATE = """\
Hello,

Thank you for contacting {company_name}. We have received your message and appreciate you reaching out.

This is an automated acknowledgement to confirm receipt of your email. A member of our team will review the details and respond to you as soon as possible. If your matter is urgent, please reply with \"URGENT\" in the subject line or contact our support team.

Best regards,
{sender_name}
{company_name}
Email: {my_address}
"""

# Logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s [%(levelname)s] %(message)s")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
BUSINESS_EMAIL_LINE_RE = re.compile(
    r"business\s*email[:\-\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.I,
)

def is_auto_generated(msg):
    """Return True if message looks like an auto-generated message we should not reply to."""
    auto_submitted = (msg.get("Auto-Submitted") or "").lower()
    if auto_submitted and auto_submitted != "no":
        return True
    precedence = (msg.get("Precedence") or "").lower()
    if precedence in ("bulk", "list", "auto_reply"):
        return True
    # common list or unsubscribe headers indicate mass mail
    if msg.get("List-Id") or msg.get("List-Unsubscribe"):
        return True
    # avoid mailer-daemon/bounce
    from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
    if from_addr and ("mailer-daemon" in from_addr.lower() or "postmaster" in from_addr.lower()):
        return True
    return False

def get_text_from_message(msg):
    """Return best-effort plain-text representation: prefer text/plain, fall back to stripped text/html."""
    if msg.is_multipart():
        # prefer text/plain
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    return part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True)
                    return payload.decode(errors="ignore") if payload else ""
        # fallback: text/html -> strip tags
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    html = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True)
                    html = payload.decode(errors="ignore") if payload else ""
                # simple strip of tags (for a robust solution, use html2text or BeautifulSoup)
                text = re.sub(r"<[^>]+>", "", html)
                return text
        return ""
    else:
        try:
            return msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True)
            return payload.decode(errors="ignore") if payload else ""

def decode_subject(subject_header):
    if not subject_header:
        return ""
    try:
        return str(make_header(decode_header(subject_header)))
    except Exception:
        return subject_header

def fetch_unseen_messages(imap_host, imap_port, username, password):
    """
    Connects to IMAP, fetches UNSEEN messages and returns a list of dicts with:
    msg_num, from_addr, from_name, subject, body, raw_message
    """
    messages = []
    try:
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap.login(username, password)
        imap.select("INBOX")
        status, data = imap.search(None, 'UNSEEN')
        if status != "OK":
            logging.warning("IMAP search failed: %s %s", status, data)
            imap.logout()
            return []
        for num in data[0].split():
            if not num:
                continue
            typ, msg_data = imap.fetch(num, "(RFC822 FLAGS)")
            if typ != "OK":
                logging.warning("Failed to fetch %s", num)
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=policy.default)
            from_header = msg.get("From", "")
            from_name, from_addr = email.utils.parseaddr(from_header)
            subject = decode_subject(msg.get("Subject", ""))
            body = get_text_from_message(msg)
            messages.append({
                "msg_num": num.decode() if isinstance(num, bytes) else str(num),
                "from_addr": from_addr,
                "from_name": from_name,
                "subject": subject,
                "body": body,
                "raw_message": msg,
            })
        imap.logout()
    except Exception as e:
        logging.exception("Error fetching messages: %s", e)
    return messages

def send_email_smtp(smtp_host, smtp_port, username, password, subject, body, from_addr, to_addrs, in_reply_to=None):
    """
    Sends an email via SMTP_SSL. Returns True on success, False on failure.
    Respects TEST_MODE to avoid sending real mail during tests.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    msg.set_content(body)

    if TEST_MODE:
        logging.info("[TEST MODE] Would send email to %s with subject %s", to_addrs, subject)
        return True

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(username, password)
            server.send_message(msg)
        logging.info("Sent auto-reply to %s", to_addrs)
        return True
    except (smtplib.SMTPException, gaierror) as e:
        logging.exception("SMTP send failed: %s", e)
        return False

def extract_business_email(body):
    """
    Try strict 'Business email' capture first; fallback to scanning near the phrase
    or a generic email scan near 'business' / 'email' keywords.
    """
    if not body:
        return None
    # direct line pattern
    m = BUSINESS_EMAIL_LINE_RE.search(body)
    if m:
        candidate = m.group(1).strip()
        if EMAIL_RE.match(candidate):
            return candidate
    # loose: find line that mentions "business" and "email" and an email near it
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if "business" in line.lower() and "email" in line.lower():
            # try to find email in the same line
            m2 = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", line)
            if m2:
                candidate = m2.group(1)
                if EMAIL_RE.match(candidate):
                    return candidate
            # try neighboring lines
            if i + 1 < len(lines):
                m3 = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", lines[i + 1])
                if m3:
                    candidate = m3.group(1)
                    if EMAIL_RE.match(candidate):
                        return candidate
    return None

def auto_reply_if_business(imap_host, imap_port, smtp_host, smtp_port, username, password,
                           reply_subject_prefix, reply_body_template):
    """
    High-level function that:
      - fetches unseen messages
      - for each message, checks auto-generated headers
      - extracts 'Business email'
      - sends reply and marks the message as Answered/Seen
    """
    new_messages = fetch_unseen_messages(imap_host, imap_port, username, password)
    if not new_messages:
        logging.info("No new messages to process right now.")
        return

    # Open an IMAP connection to update flags after sending replies
    try:
        imap_conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap_conn.login(username, password)
        imap_conn.select("INBOX")
    except Exception as e:
        logging.exception("Failed to open IMAP connection for flag updates: %s", e)
        return

    for msg_info in new_messages:
        msg_num = msg_info["msg_num"]
        subject = msg_info["subject"] or ""
        body = msg_info["body"] or ""
        raw_msg = msg_info["raw_message"]

        logging.info("Processing message %s from %s (subject: %s)", msg_num, msg_info["from_addr"], subject)

        # Skip auto-generated or list messages
        try:
            if is_auto_generated(raw_msg):
                logging.info("Skipping auto-generated or list message: %s", msg_num)
                imap_conn.store(msg_num, "+FLAGS", "\\Seen")
                continue
        except Exception:
            logging.exception("Error checking auto-generated headers; continuing.")

        # Extract business email
        business_email = extract_business_email(body)
        if not business_email:
            logging.info("No business email found in message %s; marking Seen and skipping.", msg_num)
            imap_conn.store(msg_num, "+FLAGS", "\\Seen")
            continue

        # Validate and avoid replying to self
        if not EMAIL_RE.match(business_email):
            logging.warning("Extracted business email '%s' is invalid. Skipping message %s.", business_email, msg_num)
            imap_conn.store(msg_num, "+FLAGS", "\\Seen")
            continue

        if business_email.lower() == (username or "").lower():
            logging.info("Extracted business email matches the sender account; skipping to avoid loop.")
            imap_conn.store(msg_num, "+FLAGS", "\\Seen")
            continue

        # Prepare reply
        reply_subject = reply_subject_prefix + subject
        reply_body = reply_body_template.format(
            company_name=COMPANY_NAME,
            sender_name=SENDER_NAME,
            my_address=username or "noreply@" + (os.getenv("IMAP_HOST") or "example.com"),
        )
        in_reply_to = raw_msg.get("Message-ID")

        # Send reply
        sent = send_email_smtp(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            subject=reply_subject,
            body=reply_body,
            from_addr=username,
            to_addrs=[business_email],
            in_reply_to=in_reply_to,
        )

        if sent:
            # mark as answered and seen
            try:
                imap_conn.store(msg_num, "+FLAGS", "\\Answered \\Seen")
                logging.info("Marked message %s as Answered/Seen", msg_num)
            except Exception:
                logging.exception("Failed to mark message %s flags after sending reply.", msg_num)
        else:
            # if sending failed, mark as Seen so it doesn't continuously retry immediately
            try:
                imap_conn.store(msg_num, "+FLAGS", "\\Seen")
            except Exception:
                logging.exception("Failed to mark message %s Seen after failed send.", msg_num)

    try:
        imap_conn.logout()
    except Exception:
        pass

if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        logging.error("OUTLOOK_USERNAME and OUTLOOK_APP_PASSWORD must be set in the environment.")
        raise SystemExit(1)

    logging.info("=== Starting Auto-Reply Bot for %s (%s) ===", SENDER_NAME, COMPANY_NAME)
    logging.info("Monitoring inbox for: %s", USERNAME)

    try:
        while True:
            try:
                auto_reply_if_business(
                    imap_host=IMAP_HOST,
                    imap_port=IMAP_PORT,
                    smtp_host=SMTP_HOST,
                    smtp_port=SMTP_PORT,
                    username=USERNAME,
                    password=PASSWORD,
                    reply_subject_prefix=REPLY_SUBJECT_PREFIX,
                    reply_body_template=REPLY_BODY_TEMPLATE,
                )
            except Exception:
                logging.exception("Unexpected error during auto-reply cycle.")
            logging.info("Sleeping for %s seconds...", POLL_INTERVAL_SECONDS)
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Interrupted by user. Exiting cleanly.")
