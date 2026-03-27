import os

from e2b import Sandbox

from src.core.config import settings


def kill_all():
    api_key = os.getenv("E2B_API_KEY") or settings.E2B_API_KEY
    if not api_key:
        print("No E2B API key found.")
        return

    print(f"Checking for sandboxes with API key: {api_key[:5]}...")
    try:
        paginator = Sandbox.list(api_key=api_key)
        count = 0
        while True:
            items = paginator.next_items()
            if not items:
                break
            for s in items:
                print(f"Killing sandbox: {s.sandbox_id}")
                try:
                    # SandboxInfo doesn't have .kill(), we must connect/get it first
                    Sandbox.connect(s.sandbox_id, api_key=api_key).kill()
                    count += 1
                except Exception as e:
                    print(f"Failed to kill {s.sandbox_id}: {e}")
        print(f"Successfully killed {count} sandboxes.")
    except Exception as e:
        print(f"Error listing sandboxes: {e}")


if __name__ == "__main__":
    kill_all()
