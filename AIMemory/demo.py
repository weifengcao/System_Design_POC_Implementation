import requests
import uuid
import json

import time

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "change-me-in-prod"}

def print_step(step, msg):
    print(f"\n[Step {step}] {msg}")
    print("-" * 40)

def run_demo():
    session_id = str(uuid.uuid4())
    print(f"Starting Demo Session: {session_id}")

    # 1. Add Memories
    print_step(1, "Adding Memories (Async)")
    memories = [
        "I am a software engineer living in San Francisco.",
        "My favorite programming language is Python.",
        "I am allergic to peanuts.",
        "My email is weifeng@example.com (PII test)"
    ]
    
    for text in memories:
        res = requests.post(f"{BASE_URL}/memory", json={
            "text": text,
            "session_id": session_id,
            "user_id": "demo_user"
        }, headers=HEADERS)
        
        if res.status_code == 200:
            task_id = res.json().get("task_id")
            print(f"Queued: {text[:30]}... (Task ID: {task_id})")
        else:
            print(f"Failed to add: {text} - {res.text}")
            
    print("\nWaiting for workers to process...")
    time.sleep(2) # Wait for Celery worker

    # 2. Semantic Search
    print_step(2, "Semantic Search")
    queries = [
        "Where does the user live?",
        "What language do I like?",
        "Any food restrictions?",
        "What is my email?"
    ]
    
    for q in queries:
        print(f"Query: {q}")
        res = requests.post(f"{BASE_URL}/memory/search", json={
            "query": q,
            "session_id": session_id,
            "limit": 1
        }, headers=HEADERS)
        
        if res.status_code == 200:
            results = res.json()
            if results:
                print(f"Answer Context: {results[0]['text']} (Distance: {results[0].get('distance')})")
            else:
                print("No results found.")
        else:
            print(f"Search failed: {res.text}")
        print("")

    # 3. History
    print_step(3, "Session History")
    res = requests.get(f"{BASE_URL}/sessions/{session_id}/history", headers=HEADERS)
    if res.status_code == 200:
        history = res.json()
        print(f"Total memories in session: {len(history)}")
    else:
        print(f"Failed to get history: {res.text}")

if __name__ == "__main__":
    # Ensure server is running before executing this
    print("Make sure docker-compose is running!")
    try:
        # Simple check
        requests.get("http://localhost:8000/docs")
        run_demo()
    except requests.exceptions.ConnectionError:
        print("Error: Server is not running. Please run 'docker-compose up' in a separate terminal.")
