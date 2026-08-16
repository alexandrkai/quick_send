
# app/utils/email_provider.py
def send_email(email: str, subject: str, body: str):
    # Здесь интеграция с SMTP или email-сервисом
    print(f"Email to {email}: {subject} - {body}")  # заглушка