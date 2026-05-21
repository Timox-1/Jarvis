"""
Yandex Mail via IMAP (read) + SMTP (send).
Requires app-password stored in user_memory as 'yandex_app_password'.
Yandex login stored as 'yandex_login' (set during Calendar OAuth).
"""

import imaplib
import smtplib
import email as email_lib
from email.mime.text import MIMEText
from email.header import decode_header
from db.client import get_db

IMAP_HOST = "imap.yandex.ru"
SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465


def _get_credentials(user_id: str) -> tuple[str, str]:
    db = get_db()

    # app-password from user_memory
    memory = (db.table("user_memory")
              .select("key, value")
              .eq("user_id", user_id)
              .eq("key", "yandex_app_password")
              .execute()).data
    password = memory[0]["value"] if memory else None

    # yandex_login from user_integrations (set during Calendar OAuth)
    integration = (db.table("user_integrations")
                   .select("yandex_login")
                   .eq("user_id", user_id)
                   .eq("provider", "yandex_calendar")
                   .execute()).data
    login = integration[0]["yandex_login"] if integration else None

    if not login:
        raise ValueError("Яндекс аккаунт не подключён. Используй /connect_calendar")
    if not password:
        raise ValueError("Яндекс app-password не настроен. Скажи мне: «Сохрани мой Яндекс app-password: XXXX»")

    return login, password


def _decode_str(raw: str) -> str:
    parts = decode_header(raw or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def list_emails(user_id: str, folder: str = "INBOX", limit: int = 10) -> list[dict]:
    login, password = _get_credentials(user_id)

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(login, password)
        imap.select(folder)

        _, msg_ids = imap.search(None, "ALL")
        ids = msg_ids[0].split()[-limit:][::-1]

        result = []
        for msg_id in ids:
            _, data = imap.fetch(msg_id, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
            header_raw = data[0][1]
            msg = email_lib.message_from_bytes(header_raw)
            result.append({
                "id": msg_id.decode(),
                "from": _decode_str(msg.get("From", "")),
                "subject": _decode_str(msg.get("Subject", "(без темы)")),
                "date": msg.get("Date", ""),
            })

    return result


def read_email(user_id: str, email_id: str, folder: str = "INBOX") -> dict:
    login, password = _get_credentials(user_id)

    with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
        imap.login(login, password)
        imap.select(folder)

        _, data = imap.fetch(email_id.encode(), "(RFC822)")
        msg = email_lib.message_from_bytes(data[0][1])

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(errors="replace")
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")

        return {
            "from": _decode_str(msg.get("From", "")),
            "subject": _decode_str(msg.get("Subject", "")),
            "date": msg.get("Date", ""),
            "body": body[:3000],
        }


def send_email(user_id: str, to: str, subject: str, body: str) -> str:
    login, password = _get_credentials(user_id)

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = login
    msg["To"] = to
    msg["Subject"] = subject

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(login, password)
        smtp.sendmail(login, [to], msg.as_string())

    return f"Письмо отправлено на {to}"
