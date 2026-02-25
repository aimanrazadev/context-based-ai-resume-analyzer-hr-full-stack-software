import os
import smtplib
from email.message import EmailMessage
import sys


def _env_bool(name: str, default: str = "1") -> bool:
    v = (os.getenv(name, default) or default).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def send_interview_scheduled_email(
    *,
    to_email: str,
    candidate_name: str | None,
    recruiter_name: str | None,
    job_title: str | None,
    scheduled_at_text: str,
    timezone: str | None,
    mode: str | None,
    meeting_link: str | None,
    location: str | None,
) -> None:
    """
    Sends an interview schedule notification email using SMTP (Gmail App Password recommended).

    Env vars:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TLS
    """
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int((os.getenv("SMTP_PORT") or "587").strip())
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    mail_from = (os.getenv("SMTP_FROM") or user).strip()
    use_tls = _env_bool("SMTP_TLS", "1")

    print(f"[EMAIL DEBUG] host={host}, port={port}, user={user}, pass_len={len(password)}, from={mail_from}, tls={use_tls}", file=sys.stderr)

    if not host or not user or not password or not mail_from:
        err = "SMTP is not configured (missing SMTP_HOST/SMTP_USER/SMTP_PASS/SMTP_FROM)."
        print(f"[EMAIL ERROR] {err}", file=sys.stderr)
        raise RuntimeError(err)

    cand = (candidate_name or "Candidate").strip()
    rec = (recruiter_name or "Recruiter").strip()
    jt = (job_title or "the role").strip()
    tz = (timezone or "UTC").strip()
    md = (mode or "Interview").strip()

    lines: list[str] = []
    lines.append(f"Hi {cand},")
    lines.append("")
    lines.append(f"Good news — {rec} has scheduled an interview for {jt}.")
    lines.append("")
    lines.append(f"When: {scheduled_at_text} ({tz})")
    lines.append(f"Mode: {md}")
    if meeting_link:
        lines.append(f"Meeting link: {meeting_link}")
    if location:
        lines.append(f"Location: {location}")
    lines.append("")
    lines.append("You can also view this in the Interviews section of StudentsNaukri.")
    lines.append("")
    lines.append("Best regards,")
    lines.append("StudentsNaukri")

    msg = EmailMessage()
    msg["Subject"] = f"Interview scheduled — {jt}"
    msg["From"] = mail_from
    msg["To"] = to_email
    msg.set_content("\n".join(lines))

    try:
        print(f"[EMAIL] Connecting to {host}:{port} (TLS={use_tls})...", file=sys.stderr)
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.ehlo()
            if use_tls:
                print(f"[EMAIL] Starting TLS...", file=sys.stderr)
                smtp.starttls()
                smtp.ehlo()
            print(f"[EMAIL] Logging in as {user}...", file=sys.stderr)
            smtp.login(user, password)
            print(f"[EMAIL] Sending to {to_email}...", file=sys.stderr)
            smtp.send_message(msg)
            print(f"[EMAIL] ✓ Email sent successfully to {to_email}", file=sys.stderr)
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email: {type(e).__name__}: {str(e)}", file=sys.stderr)
        raise

