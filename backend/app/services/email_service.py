"""
Email sending via smtplib — Python's standard library, so no new
package is needed. Runs the blocking SMTP call in a thread
(asyncio.to_thread) so it doesn't block the event loop that's serving
every other request while an email is being sent.

SETUP (Gmail, the quickest option for a student project):
1. Go to your Google Account -> Security -> 2-Step Verification (must
   be enabled first).
2. Go to Security -> App passwords. Create one for "Mail".
3. In backend/.env, set:
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=587
     SMTP_USERNAME=your.email@gmail.com
     SMTP_PASSWORD=<the 16-character app password, NOT your normal Gmail password>
     SMTP_FROM_EMAIL=your.email@gmail.com

If SMTP_USERNAME/SMTP_PASSWORD are left blank, send_email() logs a
warning and skips sending rather than crashing — the same
graceful-degradation pattern used for the AI providers in Phase 9, so
you can develop and test everything else without email configured.
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("equityengine.email")


def _send_sync(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning(
            "SMTP not configured (SMTP_USERNAME/SMTP_PASSWORD blank in .env) — "
            f"skipping email to {to_email}: '{subject}'"
        )
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME}>"
    message["To"] = to_email
    message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USERNAME, to_email, message.as_string())
        return True
    except Exception as e:
        # Email failure should never break the calling flow (e.g. a
        # candidate's registration must still succeed even if the
        # welcome email fails to send) — log and return False rather
        # than raising.
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    if not text_body:
        text_body = "This email requires an HTML-capable email client to view properly."
    return await asyncio.to_thread(_send_sync, to_email, subject, html_body, text_body)


# ---------------------------------------------------------------------
# Shared template wrapper — keeps every email visually consistent
# without needing a templating engine dependency.
# ---------------------------------------------------------------------

def _wrap_template(title: str, body_html: str, cta_text: str = None, cta_url: str = None) -> str:
    cta_html = ""
    if cta_text and cta_url:
        cta_html = f"""
        <a href="{cta_url}" style="display:inline-block;background:#14163A;color:#FAF8F3;
           padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;
           margin-top:16px;">{cta_text}</a>
        """
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;">
      <h2 style="color:#14163A;">{title}</h2>
      <div style="color:#33355E;font-size:14px;line-height:1.6;">{body_html}</div>
      {cta_html}
      <p style="color:#6B6F8A;font-size:12px;margin-top:32px;">
        EquityEngine — Delta State University Final Year Project
      </p>
    </div>
    """


# ---------------------------------------------------------------------
# Specific emails
# ---------------------------------------------------------------------

async def send_welcome_email(to_email: str, full_name: str, role: str) -> bool:
    first_name = full_name.split(" ")[0]
    body = f"""
    <p>Hi {first_name},</p>
    <p>Your EquityEngine account is ready. As a {role}, you can now
    {"build your Competency Profile from your CV, GitHub, and community evidence"
     if role == "candidate" else "post jobs and review candidates through the Competency Dossier"}.</p>
    """
    html = _wrap_template(
        "Welcome to EquityEngine", body, cta_text="Go to EquityEngine", cta_url=settings.FRONTEND_URL
    )
    return await send_email(to_email, "Welcome to EquityEngine", html)


async def send_password_reset_email(to_email: str, full_name: str, reset_token: str) -> bool:
    first_name = full_name.split(" ")[0]
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    body = f"""
    <p>Hi {first_name},</p>
    <p>We received a request to reset your EquityEngine password. This link expires in
    1 hour. If you didn't request this, you can safely ignore this email.</p>
    """
    html = _wrap_template("Reset your password", body, cta_text="Reset password", cta_url=reset_url)
    return await send_email(to_email, "Reset your EquityEngine password", html)


async def send_application_status_email(to_email: str, full_name: str, job_title: str, status: str) -> bool:
    first_name = full_name.split(" ")[0]
    body = f"""
    <p>Hi {first_name},</p>
    <p>Your application for <strong>{job_title}</strong> has been updated to:
    <strong>{status}</strong>.</p>
    """
    html = _wrap_template(
        "Application update", body, cta_text="View application",
        cta_url=f"{settings.FRONTEND_URL}/candidate/applications",
    )
    return await send_email(to_email, f"Application update: {job_title}", html)


async def send_profile_revealed_email(to_email: str, full_name: str, job_title: str) -> bool:
    first_name = full_name.split(" ")[0]
    body = f"""
    <p>Hi {first_name},</p>
    <p>A recruiter has viewed your full profile for <strong>{job_title}</strong> —
    this typically means they're seriously considering your application.</p>
    """
    html = _wrap_template(
        "Your profile was viewed", body, cta_text="View job",
        cta_url=f"{settings.FRONTEND_URL}/candidate/applications",
    )
    return await send_email(to_email, f"Your profile was reviewed: {job_title}", html)
