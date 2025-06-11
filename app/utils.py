import qrcode
import io
import base64
import smtplib
from email.message import EmailMessage
import os
import logging

def generate_qr_code(data: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return f"data:image/png;base64,{qr_base64}"

def send_email(subject, html_content, to_email):
    """Send an email if credentials are configured.

    The function logs any exception and returns ``True`` on success and
    ``False`` if the email could not be sent. This prevents unexpected
    server errors when email credentials are missing or invalid.
    """

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_FROM')
    msg['To'] = to_email
    msg.set_content("Ez egy HTML formátumú e-mail.")
    msg.add_alternative(html_content, subtype='html')

    email_from = os.getenv('EMAIL_FROM')
    email_password = os.getenv('EMAIL_PASSWORD')

    if not email_from or not email_password:
        logging.error('Email credentials are not configured.')
        return False

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_from, email_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logging.error('Failed to send email: %s', exc)
        return False
