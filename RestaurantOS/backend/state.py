from typing import List, Dict
from models import Order, InventoryItem, MenuItem, OrderStatus
import time

class RestaurantState:
    def __init__(self):
        self.orders: List[Order] = []
        self.inventory: Dict[str, InventoryItem] = {}
        self.menu: Dict[str, MenuItem] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        # Initialize Inventory
        self.inventory["Bun"] = InventoryItem(name="Bun", quantity=20)
        self.inventory["Patty"] = InventoryItem(name="Patty", quantity=20)
        self.inventory["Lettuce"] = InventoryItem(name="Lettuce", quantity=20)
        self.inventory["Tomato"] = InventoryItem(name="Tomato", quantity=20)
        self.inventory["Cheese"] = InventoryItem(name="Cheese", quantity=20)
        
        # Initialize Menu
        self.menu["Burger"] = MenuItem(
            name="Burger",
            ingredients={"Bun": 1, "Patty": 1, "Lettuce": 1, "Tomato": 1}
        )
        self.menu["Cheeseburger"] = MenuItem(
            name="Cheeseburger",
            ingredients={"Bun": 1, "Patty": 1, "Lettuce": 1, "Tomato": 1, "Cheese": 1}
        )

    def add_order(self, order: Order):
        order.created_at = time.time()
        self.orders.append(order)

    def get_order(self, order_id: str) -> Order:
        for order in self.orders:
            if order.id == order_id:
                return order
        return None

    def update_inventory(self, item_name: str, quantity_change: int):
        if item_name in self.inventory:
            self.inventory[item_name].quantity += quantity_change

    def get_state(self):
        return {
            "orders": [o.dict() for o in self.orders],
            "inventory": [i.dict() for i in self.inventory.values()],
            "menu": [m.dict() for m in self.menu.values()]
        }

# Global State Instance
state = RestaurantState()
