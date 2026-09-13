from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.models.models import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=Union[BaseModel, Dict[str, Any]])
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=Union[BaseModel, Dict[str, Any]])
FilterSchemaType = TypeVar("FilterSchemaType", bound=Union[BaseModel, Dict[str, Any]])


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Union[Any, List[Any]]] = None,
        **kwargs
    ) -> List[ModelType]:
        query = db.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                query = query.filter(column.is_(None) if value is None else column == value)

        if order_by is not None:
            if isinstance(order_by, list):
                query = query.order_by(*order_by)
            else:
                query = query.order_by(order_by)

        return query.offset(skip).limit(limit).all()

    def filter(
        self,
        db: Session,
        *,
        filter_in: Optional[FilterSchemaType] = None,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Union[Any, List[Any]]] = None,
        **kwargs
    ) -> List[ModelType]:
        query = db.query(self.model)

        filters: Dict[str, Any] = {}
        if filter_in is not None:
            if isinstance(filter_in, dict):
                filters = filter_in
            elif hasattr(filter_in, "model_dump"):  # Pydantic v2
                filters = filter_in.model_dump(exclude_unset=True)
            elif hasattr(filter_in, "dict"):        # Pydantic v1 fallback
                filters = filter_in.dict(exclude_unset=True)

        merged_filters = {**filters, **kwargs}

        for key, value in merged_filters.items():
            if hasattr(self.model, key):
                column = getattr(self.model, key)
                query = query.filter(column.is_(None) if value is None else column == value)

        if order_by is not None:
            if isinstance(order_by, list):
                query = query.order_by(*order_by)
            else:
                query = query.order_by(order_by)

        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        if isinstance(obj_in, dict):
            create_data = obj_in
        elif hasattr(obj_in, "model_dump"):  # Pydantic v2
            create_data = obj_in.model_dump()
        elif hasattr(obj_in, "dict"):        # Pydantic v1 fallback
            create_data = obj_in.dict()
        else:
            create_data = dict(obj_in)

        db_obj = self.model(**create_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        elif hasattr(obj_in, "model_dump"):  # Pydantic v2
            update_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, "dict"):        # Pydantic v1 fallback
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = dict(obj_in)

        # Получаем реальные имена колонок таблицы через инспектор модели без сериализации связей
        columns = {c.key for c in inspect(self.model).columns}

        for field, value in update_data.items():
            if field in columns:
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> Optional[ModelType]:
        # В SQLAlchemy 2.0+ метод .get() у Session предпочтительнее db.query(...).get()
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj