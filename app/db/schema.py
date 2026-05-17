from pydantic import BaseModel, Field
from typing import Optional, Union, List, Dict

class DocumentModel(BaseModel):
    """
    Base ArangodDocument model.
    """
    key_: Optional[str] = Field(alias="_key")
    #rev_: Optional[str] = Field(alias="_rev")

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
    name: str
    github: str
    admin: bool
    email: str
    editor: List[str]

class Term(DocumentModel):
    """
    A term
    """
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
    name: str
    description: str
    
