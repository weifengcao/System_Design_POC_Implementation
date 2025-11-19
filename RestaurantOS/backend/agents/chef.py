import asyncio
from .base import BaseAgent
from state import state, OrderStatus

class ChefAgent(BaseAgent):
    def __init__(self):
        super().__init__("Chef")

    async def run(self):
        self.log("Starting shift...")
        while True:
            # Find a pending order
            pending_order = None
            for order in state.orders:
                if order.status == OrderStatus.PENDING:
                    pending_order = order
                    break
            
            if pending_order:
                self.log(f"Found pending order: {pending_order.id} ({pending_order.items})")
                
                # Check ingredients
                can_cook = True
                for item_name in pending_order.items:
                    menu_item = state.menu.get(item_name)
                    if not menu_item:
                        self.log(f"Unknown item: {item_name}")
                        can_cook = False
                        break
                    
                    for ing, qty in menu_item.ingredients.items():
                        if state.inventory[ing].quantity < qty:
                            self.log(f"Missing ingredient: {ing} for {item_name}")
                            can_cook = False
                            break
                
                if can_cook:
                    self.log(f"Cooking order {pending_order.id}...")
                    pending_order.status = OrderStatus.COOKING
                    
                    # Deduct ingredients
                    for item_name in pending_order.items:
                        menu_item = state.menu.get(item_name)
                        for ing, qty in menu_item.ingredients.items():
                            state.update_inventory(ing, -qty)
                    
                    # Simulate cooking time
                    await asyncio.sleep(5) 
                    
                    pending_order.status = OrderStatus.READY
                    self.log(f"Order {pending_order.id} is READY!")
                else:
                    self.log(f"Cannot cook order {pending_order.id} due to missing ingredients.")
                    await asyncio.sleep(2) # Wait for restock
            else:
                # self.log("No pending orders.")
                await asyncio.sleep(1)
