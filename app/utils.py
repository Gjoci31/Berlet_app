import qrcode
import io
import base64
import smtplib
from email.message import EmailMessage
import os

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
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_FROM')
    msg['To'] = to_email
    msg.set_content("Ez egy HTML formátumú e-mail.")
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(os.getenv('EMAIL_FROM'), os.getenv('EMAIL_PASSWORD'))
        smtp.send_message(msg)