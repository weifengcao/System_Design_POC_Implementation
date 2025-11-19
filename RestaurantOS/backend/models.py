from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    COOKING = "COOKING"
    READY = "READY"
    SERVED = "SERVED"

class InventoryItem(BaseModel):
    name: str
    quantity: int
    low_stock_threshold: int = 5

class MenuItem(BaseModel):
    name: str
    ingredients: Dict[str, int]  # Ingredient name -> quantity needed

class Order(BaseModel):
    id: str
    items: List[str]  # List of menu item names
    status: OrderStatus = OrderStatus.PENDING
    table_id: int
    created_at: float = 0.0
