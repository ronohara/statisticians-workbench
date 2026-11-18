"""
Email module — P2 Group 5 (Prisma-removal plan), items 20/21/22.

Faithful port of `frontend/lib/email.ts` for the backend. This is NOT an MTA —
it composes a simple RFC822 message and pipes it to the system's sendmail
binary exactly as nodemailer's sendmail transport does:

    sendmail -i -f <from> <recipient...>

with the message on stdin. Zero exit = success; non-zero = raise (which the
caller maps to a 500). The frontend's sendmail transport treats code 127
("command not found") and any other non-zero identically (both -> error), so
the backend mirrors that with a single non-zero check.

Translation lookups here are a SINGLE-language direct query against the
Translation table (value or fallback, no English-chain) — this mirrors
email.ts's `getTranslation` exactly, which is deliberately NOT the shared
`t()` chain.

Caching: getGlobalSettings mirrors email.ts's 60-second module-level cache.
"""

import asyncio
import re
import subprocess
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SENDMAIL_PATH = "/usr/sbin/sendmail"

_cached_settings = None
_cached_expiry = 0.0


async def get_global_settings(db_pool):
    """email.ts getGlobalSettings: cached 60s, emailSender/publicUrl with the
    same defaults."""
    global _cached_settings, _cached_expiry
    now = time.monotonic()
    if _cached_settings is not None and now < _cached_expiry:
        return _cached_settings

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "emailSender", "publicUrl" FROM "GlobalSettings" WHERE id = 1'
        )
    sender = (row["emailSender"] if row else None) or "no-reply@replace-with-your-domain"
    url = (row["publicUrl"] if row else None) or "https://replace-with-your-external-host-name"

    _cached_settings = {"emailSender": sender, "publicUrl": url}
    _cached_expiry = now + 60.0
    return _cached_settings


async def get_translation(db_pool, language, key, fallback):
    """email.ts getTranslation: single-language lookup, value or fallback."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT value FROM "Translation" WHERE "key" = $1 AND language = $2',
            key, language,
        )
    return row["value"] if row else fallback


async def _sendmail(from_addr, to_addrs, subject, html):
    """nodemailer sendmail transport: -i -f <from> <to...>, message on stdin.
    Non-zero exit -> RuntimeError (caller maps to 500)."""
    msg = (
        f"From: {from_addr}\n"
        f"To: {', '.join(to_addrs)}\n"
        f"Subject: {subject}\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/html; charset=utf-8\n"
        "Content-Transfer-Encoding: 8bit\n"
        "\n"
        f"{html}\n"
    )
    proc = await asyncio.to_thread(
        subprocess.run,
        [SENDMAIL_PATH, "-i", "-f", from_addr, *to_addrs],
        input=msg.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"sendmail exited with code {proc.returncode}")


async def send_verification_email(db_pool, to, token, language="en"):
    settings = await get_global_settings(db_pool)
    from_addr = settings["emailSender"]
    public_url = settings["publicUrl"]
    verification_link = f"{public_url}/verify-email?token={token}"

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            'SELECT name, email, language FROM "User" WHERE email = $1', to
        )
    user_name = (user["name"] if user else None) or "Unknown user"
    user_email = (user["email"] if user else None) or to
    user_language = (user["language"] if user else None) or language

    user_subject = await get_translation(db_pool, user_language, "email.verification.subject", "Verify your email address")
    user_greeting = await get_translation(db_pool, user_language, "email.verification.greeting", "Hello,")
    user_body = await get_translation(db_pool, user_language, "email.verification.body", "Please click the link below to verify your email address:")
    user_link_text = await get_translation(db_pool, user_language, "email.verification.link_text", "Verify Email Address")
    user_expiry = await get_translation(db_pool, user_language, "email.verification.expiry", "This link will expire in 24 hours.")
    user_ignore = await get_translation(db_pool, user_language, "email.verification.ignore", "If you did not create an account, you can ignore this email.")

    user_html = (
        f"<h1>{user_subject}</h1>\n"
        f"<p>{user_greeting}</p>\n"
        f"<p>{user_body}</p>\n"
        f'<p><a href="{verification_link}">{user_link_text}</a></p>\n'
        f"<p>{user_expiry}</p>\n"
        f"<p>{user_ignore}</p>"
    )

    await _sendmail(from_addr, [to], user_subject, user_html)

    # Admin BCC: isAdmin AND emailVerified NOT NULL AND bccRegistrations.
    async with db_pool.acquire() as conn:
        admins = await conn.fetch(
            'SELECT email, language FROM "User" '
            'WHERE "isAdmin" = true AND "emailVerified" IS NOT NULL AND "bccRegistrations" = true'
        )

    for admin in admins:
        admin_lang = admin["language"] or "en"

        admin_subject = await get_translation(db_pool, admin_lang, "email.admin_registration.subject", "New user registration request")
        admin_greeting = await get_translation(db_pool, admin_lang, "email.admin_registration.greeting", "Dear Admin,")
        admin_body = await get_translation(db_pool, admin_lang, "email.admin_registration.body", "A new user has requested registration. Details below:")
        admin_user_details = await get_translation(db_pool, admin_lang, "email.admin_registration.user_details", "User name: {name}\nUser email: {email}")
        admin_link_text = await get_translation(db_pool, admin_lang, "email.admin_registration.link_text", "Verification link (for your reference): {link}")
        admin_closing = await get_translation(db_pool, admin_lang, "email.admin_registration.closing", "You do not need to take any action unless you suspect fraud.")
        copy_of_user_email = await get_translation(db_pool, admin_lang, "email.admin_registration.copy_of_user_email", "Copy of the email sent to the user:")

        formatted_user_details = admin_user_details.replace("{name}", user_name).replace("{email}", user_email)
        formatted_link_text = admin_link_text.replace("{link}", verification_link)

        admin_html = (
            f"<h1>{admin_subject}</h1>\n"
            f"<p>{admin_greeting}</p>\n"
            f"<p>{admin_body}</p>\n"
            f"<pre>{formatted_user_details}</pre>\n"
            f"<p>{formatted_link_text}</p>\n"
            f"<p>{admin_closing}</p>\n"
            "<hr>\n"
            f"<p><em>{copy_of_user_email}</em></p>\n"
            f"{user_html}"
        )

        await _sendmail(from_addr, [admin["email"]], admin_subject, admin_html)


async def send_password_reset_email(db_pool, to, token, language="en"):
    """email.ts sendPasswordResetEmail: no admin BCC (unlike verification)."""
    settings = await get_global_settings(db_pool)
    from_addr = settings["emailSender"]
    public_url = settings["publicUrl"]
    reset_link = f"{public_url}/reset-password?token={token}"

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            'SELECT language FROM "User" WHERE email = $1', to
        )
    user_language = (user["language"] if user else None) or language

    subject = await get_translation(db_pool, user_language, "email.reset_password.subject", "Reset your password")
    greeting = await get_translation(db_pool, user_language, "email.reset_password.greeting", "Hello,")
    body = await get_translation(db_pool, user_language, "email.reset_password.body", "You requested to reset your password. Click the link below to set a new password:")
    link_text = await get_translation(db_pool, user_language, "email.reset_password.link_text", "Reset Password")
    expiry = await get_translation(db_pool, user_language, "email.reset_password.expiry", "This link will expire in 24 hours.")
    ignore = await get_translation(db_pool, user_language, "email.reset_password.ignore", "If you did not request this, you can ignore this email.")

    html = (
        f"<h1>{subject}</h1>\n"
        f"<p>{greeting}</p>\n"
        f"<p>{body}</p>\n"
        f'<p><a href="{reset_link}">{link_text}</a></p>\n'
        f"<p>{expiry}</p>\n"
        f"<p>{ignore}</p>"
    )

    await _sendmail(from_addr, [to], subject, html)


# ============================================================
# Database-analysis email (item 27 — email-pdf route)
# ============================================================
# The email CONTENT keys are frontend-owned (ai.database.email_*) and are
# referenced by canonical key string with an inline English fallback — the same
# pattern as email.verification.* above, NOT re-declared as backend
# TranslationKeys.

EMAIL_CONTENT_KEYS = [
    "ai.database.email_subject",
    "ai.database.email_body_title",
    "ai.database.email_body_database",
    "ai.database.email_body_type",
    "ai.database.email_body_connection",
    "ai.database.email_body_id",
    "ai.database.email_body_attachment",
    "ai.database.email_body_signature",
]


async def fetch_email_translations(db_pool, language, keys):
    """Per-language batch primitive: fetch all keys for one language in a single
    query. Mirrors the email-pdf reference's fallback rule exactly — if the
    requested language returns ZERO rows and is not English, fall back to the
    full English set (not per-key English fallback, which is the shared t()
    chain's behaviour)."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT key, value FROM "Translation" WHERE language = $1 AND key = ANY($2)',
            language, keys,
        )
    tr = {r["key"]: r["value"] for r in rows}
    if language != "en" and not tr:
        async with db_pool.acquire() as conn:
            en_rows = await conn.fetch(
                'SELECT key, value FROM "Translation" WHERE language = \'en\' AND key = ANY($1)',
                keys,
            )
        tr = {r["key"]: r["value"] for r in en_rows}
    return tr


async def send_email_with_attachment(from_addr, to, subject, text, filename, pdf_bytes):
    """MIME multipart/mixed: plain-text body + PDF attachment, piped to sendmail.
    Non-zero exit -> RuntimeError (caller maps to 502 proxy_error)."""
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)

    proc = await asyncio.to_thread(
        subprocess.run,
        [SENDMAIL_PATH, "-i", "-f", from_addr, to],
        input=msg.as_string().encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"sendmail exited with code {proc.returncode}")


async def send_database_analysis_email(db_pool, to, language, report, pdf_bytes):
    """Compose the database-analysis email in the recipient's language and send
    it with the PDF attached. Mirrors email-pdf/route.ts: subject/body are the 8
    ai.database.email_* keys with inline English fallbacks + {db_name}/{db_type}/
    {conn_name}/{conn_id} substitution; filename uses the report's own
    connection_id (no timestamp, unlike export-pdf)."""
    settings = await get_global_settings(db_pool)
    from_addr = settings["emailSender"]

    tr = await fetch_email_translations(db_pool, language, EMAIL_CONTENT_KEYS)

    def content(key, fallback):
        return tr.get(key, fallback)

    conn_id = str(report.get("connection_id") or "unknown")
    db_name = str(report.get("database_name") or report.get("connection_name") or "Unknown")
    db_type = str(report.get("database_type") or "Unknown")
    conn_name = str(report.get("connection_name") or report.get("connection_id") or "unknown")

    subject = content(
        "ai.database.email_subject",
        "Database Design Analysis \u2014 {db_name} ({db_type}) [Connection {conn_id}]",
    ).replace("{db_name}", db_name).replace("{db_type}", db_type).replace("{conn_id}", conn_id)

    body_title = content("ai.database.email_body_title", "Database Design Analysis Report")
    body_database = content("ai.database.email_body_database", "Database: {db_name}").replace("{db_name}", db_name)
    body_type = content("ai.database.email_body_type", "Database Type: {db_type}").replace("{db_type}", db_type)
    body_connection = content("ai.database.email_body_connection", "Connection: {conn_name}").replace("{conn_name}", conn_name)
    body_id = content("ai.database.email_body_id", "Connection ID: {conn_id}").replace("{conn_id}", conn_id)
    body_attachment = content("ai.database.email_body_attachment", "Please find the analysis report attached.")
    body_signature = content("ai.database.email_body_signature", "\u2014 Statisticians Workbench")

    email_text = "\n".join([
        body_title, "",
        body_database,
        body_type,
        body_connection,
        body_id,
        "",
        body_attachment,
        "",
        body_signature,
    ])

    filename = f"database-analysis-{re.sub(r'\s+', '-', db_name)}-{conn_id}.pdf"

    await send_email_with_attachment(from_addr, to, subject, email_text, filename, pdf_bytes)
