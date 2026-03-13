"""
Frontend Application Entry Point (Simulated).
This script represents a web application that consumes the 'service_api'.
It shows cross-service communication patterns where one component relies on another's API.
The goal is to test how the RAG pipeline handles information navigation across repos.
"""

import requests
import os

class WebApp:
    """
    Simulates a client-side application logic.
    Provides methods to interact with the backend user service.
    """
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url

    def register_user(self, name: str, email: str) -> dict:
        """
        Submits a registration request to the service_api.
        
        Args:
            name (str): User display name.
            email (str): Target email address.
            
        Returns:
            dict: The JSON response from the server.
        """
        payload = {"username": name, "email": email}
        endpoint = f"{self.api_url}/api/users"
        
        print(f"DEBUG: Connection attempt to {endpoint}")
        try:
            # Simulated API call for RAG context
            response = requests.post(endpoint, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Service API unreachable. {e}")
            return {"error": str(e)}

    def check_api_status(self) -> bool:
        """Checks if the service_api is currently online."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

if __name__ == "__main__":
    # Example usage for RAG evaluation context
    client = WebApp()
    print("Testing WebApp integration...")
    # This block provides context about how the WebApp is intended to be used.
