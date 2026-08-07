from pydantic import BaseModel, Field, PrivateAttr, ConfigDict, AliasChoices
from typing import Optional, Union, List, Dict, Any
from arangoasync.database import StandardDatabase

class Change(BaseModel):
    """
    Internal class to collect batch changes
    """
    key: str
    context: str
    value: str
    n: int = 0


class DocumentModel(BaseModel):
    """
    Base Arango document model.
    """
    model_config = ConfigDict(serialize_by_alias=True)
    key: str = Field(default=None,
                     serialization_alias="_key", # Arando model
                     validation_alias=AliasChoices('_key', 'key'), # accept arango or json
                     pattern=r"^[a-zA-Z0-9_\-.@+=]+$" # restrict to valid arango keys
                     )

    
class EdgeModel(BaseModel):
    """
    Base Arango edge model.
    """
    model_config = ConfigDict(serialize_by_alias=True)
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
    admin: List[str]
    root: bool

    
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

    # Development fields
    rev: int = 1

    
class Link(EdgeModel):
    """
    A link between terms
    """
    context: str

    
class Comment(EdgeModel):
    """
    A comment by a user on a term
    """
    comment: str
    timestamp: float

    
class Tag(DocumentModel):
    """
    A tag
    """
    name: str
    description: str = ""

    
class Vocabulary(DocumentModel):
    """
    Info for a vocabulary
    """
    name: str
    description: str
    editable: bool

    def is_editable(self, user):
        """
        Is this vocabulary editable by user
        """
        return self.editable and self.key in user.editor
            
    
class Log(DocumentModel):
    """
    Log of changes
    """
    timestamp: float
    user: str
    target: str
    summary: str
    diff: str = ""

    
class Task(DocumentModel):
    """
    A task
    """
    name: str
    description: str = ""
    locked: bool = False
    order: int = 0
    
class Work(EdgeModel):
    """
    A work item on a task
    """
    content: str = ""
    
