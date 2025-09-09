from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

class Category(str, Enum):
    ENTERTAINMENT = 'entertainment'
    FOOD = 'food'
    SNACKS = 'snacks'
    HOME = 'home'
    OTHER = 'other'

@dataclass
class User:
    id: int
    username: str
    first_name: str
    last_name: Optional[str] = None

@dataclass
class Expense:
    id: int
    user_id: int
    amount: float
    category: Category
    description: str
    created_at: datetime
    comment: Optional[str] = None