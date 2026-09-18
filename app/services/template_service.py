from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import MessageTemplate, User


class TemplateRenderResult:
    def __init__(self, title: str, body: str, footer: str, full_text: str):
        self.title = title
        self.body = body
        self.footer = footer
        self.full_text = full_text  # Итоговая склейка для отправки по SMS


class SafeFormatter(dict):
    """Предотвращает KeyError при отсутствии опциональных переменных в словаре."""
    def __missing__(self, key):
        return f"{{{key}}}"


class MessageTemplateService:
    @staticmethod
    def get_effective_template(
        db: Session,
        *,
        channel_identifier_id: int,
        user_id: Optional[int] = None,
        template_id: Optional[int] = None,
    ) -> Optional[MessageTemplate]:
        """
        Иерархия поиска шаблона:
        1. Явно переданный template_id (если указан).
        2. Дефолтный активный шаблон пользователя для данного канала.
        3. Системный дефолтный шаблон (user_id IS NULL).
        """
        # 1. По конкретному ID
        if template_id:
            tpl = (
                db.query(MessageTemplate)
                .filter(
                    MessageTemplate.id == template_id,
                    MessageTemplate.is_active.is_(True),
                )
                .first()
            )
            if tpl:
                return tpl

        # 2. Дефолтный шаблон пользователя
        if user_id:
            user_tpl = (
                db.query(MessageTemplate)
                .filter(
                    MessageTemplate.user_id == user_id,
                    MessageTemplate.channel_identifier_id == channel_identifier_id,
                    MessageTemplate.is_default.is_(True),
                    MessageTemplate.is_active.is_(True),
                )
                .first()
            )
            if user_tpl:
                return user_tpl

        # 3. Системный дефолтный шаблон
        return (
            db.query(MessageTemplate)
            .filter(
                MessageTemplate.user_id.is_(None),
                MessageTemplate.channel_identifier_id == channel_identifier_id,
                MessageTemplate.is_default.is_(True),
                MessageTemplate.is_active.is_(True),
            )
            .first()
        )

    @classmethod
    def render(
        cls,
        db: Session,
        *,
        channel_identifier_id: int,
        raw_text: str,
        sender_user: Optional[User],
        opt_out_url: str,
        template_id: Optional[int] = None,
        extra_vars: Optional[Dict[str, Any]] = None,
    ) -> TemplateRenderResult:
        """Собирает и рендерит сообщение из 3 частей."""
        user_id = sender_user.id if sender_user else None
        template = cls.get_effective_template(
            db,
            channel_identifier_id=channel_identifier_id,
            user_id=user_id,
            template_id=template_id,
        )

        # Контекст подстановки переменных
        context = {
            "text": raw_text,
            "author_phone": sender_user.phone if sender_user else "",
            "author_name": (sender_user.full_name or sender_user.phone) if sender_user else "",
            "author_email": sender_user.email if sender_user else "",
            "opt_out_url": opt_out_url,
        }
        if extra_vars:
            context.update(extra_vars)

        formatter = SafeFormatter(context)

        # Если в базе совсем нет шаблонов (fallback)
        if not template:
            title = f"От {context['author_phone']}" if context['author_phone'] else ""
            body = raw_text
            footer = f"Отписаться: {opt_out_url}"
        else:
            title = template.title_template.format_map(formatter) if template.title_template else ""
            body = template.body_template.format_map(formatter)
            footer = template.footer_template.format_map(formatter) if template.footer_template else ""

        # Склейка итогового текста сообщения
        parts = [p.strip() for p in [title, body, footer] if p and p.strip()]
        full_text = "\n".join(parts)

        return TemplateRenderResult(
            title=title,
            body=body,
            footer=footer,
            full_text=full_text,
        )