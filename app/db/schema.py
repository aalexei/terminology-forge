from pydantic import BaseModel, Field, PrivateAttr, ConfigDict
from typing import Optional, Union, List, Dict, Any
from arangoasync.database import StandardDatabase

class DocumentModel(BaseModel):
    """
    Base ArangodDocument model.
    """
    model_config = ConfigDict(serialize_by_alias=True)
    key_: str = Field(alias="_key")
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
    term: str
    definition: str
    synonyms: List[str]
    notes: List[str]
    source: str
    context: str
    section: str

    src: str | None = None
    rev: int | None = None
    log: List[str] | None = None

    # Optional private keys with dynamic info on term
    #tags_: List[dict] | None = Field(None, exclude=True)
    #links_: List[dict] | None = Field(None, exclude=True)

class Tag(DocumentModel):
    """
    A tag
    """
    name: str
    description: str
    
