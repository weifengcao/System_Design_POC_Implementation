import React, { useEffect, useState } from 'react';
import { fetchState, placeOrder, resetState } from './api';

const Dashboard = () => {
    const [state, setState] = useState(null);
    const [loading, setLoading] = useState(true);

    const refreshState = async () => {
        try {
            const data = await fetchState();
            setState(data);
        } catch (error) {
            console.error("Failed to fetch state:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        refreshState();
        const interval = setInterval(refreshState, 1000); // Poll every second
        return () => clearInterval(interval);
    }, []);

    const handleOrder = async (item) => {
        await placeOrder([item], 1);
        refreshState();
    };

    const handleReset = async () => {
        await resetState();
        refreshState();
    };

    if (loading) return <div className="p-10 text-center">Loading Restaurant OS...</div>;
    if (!state) return <div className="p-10 text-center text-red-500">Error connecting to backend.</div>;

    return (
        <div className="min-h-screen bg-gray-100 p-8 font-sans text-gray-800">
            <header className="mb-8 flex justify-between items-center">
                <h1 className="text-4xl font-bold text-indigo-600">Restaurant OS</h1>
                <button onClick={handleReset} className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded shadow">
                    Reset System
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Menu Section */}
                <div className="bg-white p-6 rounded-xl shadow-lg">
                    <h2 className="text-2xl font-semibold mb-4 text-gray-700 border-b pb-2">Menu</h2>
                    <div className="space-y-3">
                        {state.menu.map((item) => (
                            <div key={item.name} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                                <span className="font-medium">{item.name}</span>
                                <button
                                    onClick={() => handleOrder(item.name)}
                                    className="bg-indigo-500 hover:bg-indigo-600 text-white px-3 py-1 rounded text-sm"
                                >
                                    Order
                                </button>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Orders Section */}
                <div className="bg-white p-6 rounded-xl shadow-lg">
                    <h2 className="text-2xl font-semibold mb-4 text-gray-700 border-b pb-2">Active Orders</h2>
                    <div className="space-y-3 max-h-[500px] overflow-y-auto">
                        {state.orders.length === 0 && <p className="text-gray-400 italic">No active orders.</p>}
                        {state.orders.slice().reverse().map((order) => (
                            <div key={order.id} className="p-4 border rounded-lg bg-gray-50">
                                <div className="flex justify-between mb-2">
                                    <span className="text-xs text-gray-500">#{order.id.slice(0, 8)}</span>
                                    <span className={`text-xs font-bold px-2 py-1 rounded ${order.status === 'READY' ? 'bg-green-100 text-green-700' :
                                            order.status === 'COOKING' ? 'bg-yellow-100 text-yellow-700' :
                                                'bg-gray-200 text-gray-700'
                                        }`}>
                                        {order.status}
                                    </span>
                                </div>
                                <div className="font-medium">{order.items.join(", ")}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Inventory Section */}
                <div className="bg-white p-6 rounded-xl shadow-lg">
                    <h2 className="text-2xl font-semibold mb-4 text-gray-700 border-b pb-2">Inventory</h2>
                    <div className="space-y-2">
                        {state.inventory.map((item) => (
                            <div key={item.name} className="flex justify-between items-center">
                                <span>{item.name}</span>
                                <div className="flex items-center gap-2">
                                    <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full ${item.quantity < 5 ? 'bg-red-500' : 'bg-green-500'}`}
                                            style={{ width: `${Math.min(item.quantity * 5, 100)}%` }}
                                        ></div>
                                    </div>
                                    <span className={`font-mono w-8 text-right ${item.quantity < 5 ? 'text-red-600 font-bold' : 'text-gray-600'}`}>
                                        {item.quantity}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
