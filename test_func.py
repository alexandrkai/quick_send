from app.services.user_document import *
from app.models import *

db=next(get_db())
service=UserDocumentService(db)
res=service.check_documents_by_phone("+79175729812")
pass