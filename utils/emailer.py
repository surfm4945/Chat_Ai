import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration Settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SENDER_EMAIL = "surfm4945@gmail.com"        # Replace with your Gmail
SENDER_PASSWORD = "yafh wcjw fzzg hlry"    # Replace with your 16-digit App Password

def send_verification_otp(recipient_email):
    """Generates a 6-digit verification code and fires it via Gmail SMTP."""
    otp_code = str(random.randint(100000, 999999))
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email
    msg['Subject'] = "🔒 Security Verification: The Mart Network"
    
    body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background: #111827; border: 1px solid #1f2937; padding: 30px; border-radius: 12px; text-align: center;">
          <h2 style="color: #38bdf8; margin-bottom: 10px;">The Mart Network</h2>
          <p style="color: #9ca3af;">Your identity registration node requested a security verification code.</p>
          <div style="background: #1f2937; padding: 15px; border-radius: 8px; font-size: 24px; font-weight: bold; letter-spacing: 4px; color: #ffffff; margin: 20px 0;">
            {otp_code}
          </div>
          <p style="font-size: 0.8rem; color: #64748b;">This link code expires shortly. If you did not execute this request, secure your credentials immediately.</p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))
    
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        return True, otp_code
    except Exception as e:
        return False, str(e)
