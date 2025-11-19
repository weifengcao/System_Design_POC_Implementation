import asyncio
from .base import BaseAgent
from state import state

class InventoryAgent(BaseAgent):
    def __init__(self):
        super().__init__("InventoryManager")

    async def run(self):
        self.log("Starting shift...")
        while True:
            # Check for low stock
            for item in state.inventory.values():
                if item.quantity < item.low_stock_threshold:
                    self.log(f"Low stock alert: {item.name} ({item.quantity}). Restocking...")
                    await asyncio.sleep(2) # Simulate restocking time
                    state.update_inventory(item.name, 20)
                    self.log(f"Restocked {item.name}. New quantity: {item.quantity}")
            
            await asyncio.sleep(5)
