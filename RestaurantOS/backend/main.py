from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List
import uuid

from models import Order, OrderStatus
from state import state
from agents.chef import ChefAgent
from agents.inventory import InventoryAgent

app = FastAPI(title="Restaurant OS POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agents
chef = ChefAgent()
inventory_manager = InventoryAgent()

@app.on_event("startup")
async def startup_event():
    # Run agents in background
    asyncio.create_task(chef.run())
    asyncio.create_task(inventory_manager.run())

@app.get("/")
def read_root():
    return {"message": "Restaurant OS Backend is running"}

@app.get("/state")
def get_state():
    return state.get_state()

@app.post("/order")
def place_order(items: List[str], table_id: int):
    order_id = str(uuid.uuid4())
    new_order = Order(id=order_id, items=items, table_id=table_id)
    state.add_order(new_order)
    return {"message": "Order placed", "order_id": order_id}

@app.post("/reset")
def reset_state():
    state.orders = []
    state._initialize_defaults()
    return {"message": "State reset"}
