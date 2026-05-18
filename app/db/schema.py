from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional, Union, List, Dict, Any
from arangoasync.database import StandardDatabase

class DocumentModel(BaseModel):
    """
    Base ArangodDocument model.
    """
    key_: Optional[str] = Field(alias="_key")
    #rev_: Optional[str] = Field(alias="_rev")

    # _db: Any = PrivateAttr(default=StandardDatabase)
    
    
class EdgeModel(BaseModel):
    """
    Base Arango edge model.
    """
    from_: Union[str, DocumentModel] = Field(alias="_from")
    to_: Union[str, DocumentModel] = Field(alias="_to")

class User(DocumentModel):
    """
    TF User
    """
    # _collection: str = "users"
    name: str
    github: str
    admin: bool
    email: str
    editor: List[str]

class Term(DocumentModel):
    """
    A term
    """
    # _collection: str = ""
    key: str
    term: str
    definition: str
    synonyms: List[str]
    notes: List[str]
    source: str
    context: str
    section: str

    src: str
    rev: int
    log: List[str]

class Tag(DocumentModel):
    """
    A tag
    """
    # _collection: str = "tags"
    name: str
    description: str
    
