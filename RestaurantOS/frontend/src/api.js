const API_URL = "http://localhost:8000";

export const fetchState = async () => {
    const response = await fetch(`${API_URL}/state`);
    return response.json();
};

export const placeOrder = async (items, tableId) => {
    const response = await fetch(`${API_URL}/order?table_id=${tableId}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(items),
    });
    return response.json();
};

export const resetState = async () => {
    const response = await fetch(`${API_URL}/reset`, {
        method: "POST",
    });
    return response.json();
};
