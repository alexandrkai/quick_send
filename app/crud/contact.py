# app/crud/contact.py

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload

from app.crud.base import CRUDBase
from app.models.models import (
    Contact,
    Person,
    PersonContactLink,
    S_Channel,
    S_ChannelIdentifier,
)
from app.schemas.schemas import ContactCreate, ContactUpdate


class CRUDContact(CRUDBase[Contact, ContactCreate, ContactUpdate]):

    def get_by_identifier_and_value(
        self,
        db: Session,
        *,
        channel_identifier_id: int,
        value: str,
        only_active: bool = False
    ) -> Optional[Contact]:
        """Получить контакт по типу идентификатора и значению."""
        query = db.query(Contact).filter(
            Contact.channel_identifier_id == channel_identifier_id,
            Contact.value == value,
        )
        if only_active:
            query = query.filter(Contact.is_active.is_(True))
        return query.first()

    def get_with_channel(self, db: Session, *, contact_id: int) -> Optional[Contact]:
        """Получить контакт с предзагруженным деревом: идентификатор и канал."""
        return (
            db.query(Contact)
            .options(
                joinedload(Contact.channel_identifier).joinedload(S_ChannelIdentifier.channel)
            )
            .filter(Contact.id == contact_id)
            .first()
        )

    def get_by_channel_and_channel_identifier(
        self,
        db: Session,
        *,
        contact_id: int,
        only_default: bool = False
    ) -> Tuple[Optional[Contact], Optional[S_Channel], Optional[S_ChannelIdentifier]]:
        """Получить кортеж (Contact, S_Channel, S_ChannelIdentifier)."""
        query = (
            db.query(Contact)
            .options(
                joinedload(Contact.channel_identifier).joinedload(S_ChannelIdentifier.channel)
            )
        )
        if only_default:
            query = query.join(Contact.channel_identifier).filter(
                S_ChannelIdentifier.is_default.is_(True)
            )

        contact = query.filter(Contact.id == contact_id).first()
        if not contact:
            return None, None, None

        identifier = contact.channel_identifier
        channel = identifier.channel if identifier else None
        return contact, channel, identifier

    def create_contact(
        self,
        db: Session,
        *,
        channel_identifier_id: int,
        value: str,
        is_active: bool = True
    ) -> Contact:
        """Создать системный контакт без привязки к персоне."""
        contact_in = ContactCreate(
            channel_identifier_id=channel_identifier_id,
            value=value,
            is_active=is_active
        )
        return self.create(db, obj_in=contact_in)

    def get_or_create(
        self,
        db: Session,
        *,
        channel_identifier_id: int,
        value: str
    ) -> Contact:
        """Найти контакт по идентификатору и значению или создать новый."""
        contact = self.get_by_identifier_and_value(
            db, channel_identifier_id=channel_identifier_id, value=value
        )
        if not contact:
            contact = self.create_contact(
                db, channel_identifier_id=channel_identifier_id, value=value
            )
        return contact

    # --- Методы привязки контакта к персоне (Person) ---

    def get_person_contact_link(
        self,
        db: Session,
        *,
        person_id: int,
        contact_id: int
    ) -> Optional[PersonContactLink]:
        """Получить связку персоны и контакта."""
        return (
            db.query(PersonContactLink)
            .filter(
                PersonContactLink.person_id == person_id,
                PersonContactLink.contact_id == contact_id
            )
            .first()
        )

    def link_to_person(
        self,
        db: Session,
        *,
        person_id: int,
        contact_id: int,
        is_primary: bool = False,
        is_active: bool = True
    ) -> PersonContactLink:
        """Привязать контакт к персоне."""
        link = self.get_person_contact_link(db, person_id=person_id, contact_id=contact_id)
        if link:
            link.is_primary = is_primary
            link.is_active = is_active
            db.add(link)
            db.commit()
            db.refresh(link)
            return link

        link = PersonContactLink(
            person_id=person_id,
            contact_id=contact_id,
            is_primary=is_primary,
            is_active=is_active
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def unlink_from_person(
        self,
        db: Session,
        *,
        person_id: int,
        contact_id: int
    ) -> bool:
        """Отвязать контакт от персоны."""
        link = self.get_person_contact_link(db, person_id=person_id, contact_id=contact_id)
        if not link:
            return False
        db.delete(link)
        db.commit()
        return True

    def set_person_contact_primary(
        self,
        db: Session,
        *,
        person_id: int,
        contact_id: int
    ) -> Optional[PersonContactLink]:
        """Сделать контакт основным для указанной персоны, сбросив флаг у остальных."""
        target_link = self.get_person_contact_link(db, person_id=person_id, contact_id=contact_id)
        if not target_link:
            return None

        # Сброс флага primary для остальных контактов этой персоны
        (
            db.query(PersonContactLink)
            .filter(
                PersonContactLink.person_id == person_id,
                PersonContactLink.contact_id != contact_id
            )
            .update({"is_primary": False})
        )
        target_link.is_primary = True
        db.add(target_link)
        db.commit()
        db.refresh(target_link)
        return target_link

    # --- Выборки по владельцу (User) через Person ---

    def get_by_user(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        only_active: bool = True
    ) -> List[Contact]:
        """Получить все контакты адресной книги пользователя через его персон."""
        query = (
            db.query(Contact)
            .join(PersonContactLink, PersonContactLink.contact_id == Contact.id)
            .join(Person, Person.id == PersonContactLink.person_id)
            .filter(Person.user_id == user_id)
        )
        if only_active:
            query = query.filter(
                Person.is_active.is_(True),
                PersonContactLink.is_active.is_(True),
                Contact.is_active.is_(True)
            )
        return query.distinct().offset(skip).limit(limit).all()

    def get_by_user_and_channel(
        self,
        db: Session,
        *,
        user_id: int,
        channel_identifier_id: int,
        only_active: bool = True
    ) -> List[Contact]:
        """Получить контакты конкретного типа (например, все телефоны) из книги пользователя."""
        query = (
            db.query(Contact)
            .join(PersonContactLink, PersonContactLink.contact_id == Contact.id)
            .join(Person, Person.id == PersonContactLink.person_id)
            .filter(
                Person.user_id == user_id,
                Contact.channel_identifier_id == channel_identifier_id
            )
        )
        if only_active:
            query = query.filter(
                Person.is_active.is_(True),
                PersonContactLink.is_active.is_(True),
                Contact.is_active.is_(True)
            )
        return query.distinct().all()


crud_contact = CRUDContact(Contact)