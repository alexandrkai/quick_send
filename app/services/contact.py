# app/services/contact.py

from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import ContactAlreadyExistsError, ContactNotFoundError
from app.crud.contact import crud_contact
from app.models.models import Contact, Person, PersonContactLink
from app.schemas.schemas import ContactCreate


class ContactService:
    def __init__(self, db: Session):
        self.db = db

    # --- Работа с физическими контактами (независимо от пользователей) ---

    def get_contact_by_id(self, contact_id: int) -> Optional[Contact]:
        """Получить физический контакт по ID."""
        return crud_contact.get(self.db, contact_id)

    def get_contact_by_identifier_and_value(
        self,
        channel_identifier_id: int,
        value: str,
        only_active: bool = False
    ) -> Optional[Contact]:
        """Получить контакт по типу идентификатора канала и значению."""
        return crud_contact.get_by_identifier_and_value(
            self.db,
            channel_identifier_id=channel_identifier_id,
            value=value,
            only_active=only_active
        )

    def create_contact(
        self,
        channel_identifier_id: int,
        value: str,
        is_active: bool = True
    ) -> Contact:
        """Создать новый системный контакт без привязки к персоне."""
        existing = self.get_contact_by_identifier_and_value(channel_identifier_id, value)
        if existing:
            raise ContactAlreadyExistsError(f"Контакт {value} уже зарегистрирован в системе")
        return crud_contact.create_contact(
            self.db,
            channel_identifier_id=channel_identifier_id,
            value=value,
            is_active=is_active
        )

    def get_or_create_contact(
        self,
        channel_identifier_id: int,
        value: str
    ) -> Contact:
        """Найти системный контакт или создать новый, если он не найден."""
        return crud_contact.get_or_create(
            self.db,
            channel_identifier_id=channel_identifier_id,
            value=value
        )

    # --- Управление связями контакта с персоной (Person) ---

    def link_contact_to_person(
        self,
        person_id: int,
        channel_identifier_id: int,
        value: str,
        is_primary: bool = False,
        is_active: bool = True
    ) -> Contact:
        """
        Найти/создать системный контакт и привязать его к карточке Person.
        """
        contact = self.get_or_create_contact(
            channel_identifier_id=channel_identifier_id,
            value=value
        )
        crud_contact.link_to_person(
            self.db,
            person_id=person_id,
            contact_id=contact.id,
            is_primary=is_primary,
            is_active=is_active
        )
        return contact

    def unlink_contact_from_person(self, person_id: int, contact_id: int) -> bool:
        """Отвязать контакт от карточки персоны."""
        return crud_contact.unlink_from_person(
            self.db,
            person_id=person_id,
            contact_id=contact_id
        )

    def set_person_contact_primary(
        self,
        person_id: int,
        contact_id: int
    ) -> PersonContactLink:
        """Установить контакт основным для персоны."""
        link = crud_contact.set_person_contact_primary(
            self.db,
            person_id=person_id,
            contact_id=contact_id
        )
        if not link:
            raise ContactNotFoundError(
                f"Связь персоны {person_id} с контактом {contact_id} не найдена"
            )
        return link

    # --- Выборки контактов пользователя (User) через Person ---

    def get_user_contacts(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        only_active: bool = True
    ) -> List[Contact]:
        """Получить все физические контакты из адресной книги клиента."""
        return crud_contact.get_by_user(
            self.db,
            user_id=user_id,
            skip=skip,
            limit=limit,
            only_active=only_active
        )

    def get_user_contacts_by_channel(
        self,
        user_id: int,
        channel_identifier_id: int,
        only_active: bool = True
    ) -> List[Contact]:
        """Получить контакты конкретного типа (например, все телефоны) из адресной книги клиента."""
        return crud_contact.get_by_user_and_channel(
            self.db,
            user_id=user_id,
            channel_identifier_id=channel_identifier_id,
            only_active=only_active
        )

    def get_contact_by_value_for_user(
        self,
        user_id: int,
        channel_identifier_id: int,
        value: str
    ) -> Optional[Contact]:
        """
        Найти контакт по значению и проверить, что он привязан хотя бы к одной
        персоне данного пользователя.
        """
        contact = self.get_contact_by_identifier_and_value(channel_identifier_id, value)
        if not contact:
            return None

        # Проверяем принадлежность контакта хотя бы к одной персоне пользователя
        is_owned = (
            self.db.query(PersonContactLink)
            .join(Person, Person.id == PersonContactLink.person_id)
            .filter(
                Person.user_id == user_id,
                PersonContactLink.contact_id == contact.id
            )
            .first()
        )
        if not is_owned:
            return None

        return contact