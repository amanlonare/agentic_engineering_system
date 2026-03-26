import os
from e2b import Sandbox
from dotenv import load_dotenv

def cleanup_sandboxes():
    load_dotenv()
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("❌ E2B_API_KEY not found in .env")
        return

    print(f"🔍 Fetching active sandboxes...")
    paginator = Sandbox.list(api_key=api_key)
    sandboxes = []
    while True:
        sandboxes.extend(paginator.next_items())
        if not paginator.has_next:
            break
    
    if not sandboxes:
        print("✅ No active sandboxes found.")
        return

    print(f"⚠️ Found {len(sandboxes)} active sandboxes. Killing them all...")
    for sb in sandboxes:
        print(f"💀 Killing {sb.sandbox_id}...")
        try:
            Sandbox.connect(sb.sandbox_id, api_key=api_key).kill()
            print(f"✅ Killed {sb.sandbox_id}")
        except Exception as e:
            print(f"❌ Failed to kill {sb.sandbox_id}: {e}")

if __name__ == "__main__":
    cleanup_sandboxes()
