import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config.config import settings

def send_feedback_email(name: str, email: str, subject: str, message: str) -> bool:
    """
    Отправляет письмо администратору с данными обратной связи.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.ADMIN_EMAIL
        msg["Subject"] = f"Обратная связь от {name}: {subject if subject else 'Без темы'}"

        body = f"""
        <h2>Новое сообщение с сайта</h2>
        <p><strong>Имя:</strong> {name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Тема:</strong> {subject or 'Не указана'}</p>
        <p><strong>Сообщение:</strong></p>
        <p>{message}</p>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Ошибка отправки письма: {e}")
        return False