import os
from e2b import Sandbox
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("E2B_API_KEY")
print(f"API Key found: {bool(api_key)}")

res = Sandbox.list(api_key=api_key)
print(f"Type of res: {type(res)}")
print(f"Attributes of res: {dir(res)}")

try:
    for item in res.next_items():
        print(f"Item: {item}")
except Exception as e:
    print(f"Failed to iterate: {e}")
