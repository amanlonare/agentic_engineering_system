import os

from dotenv import load_dotenv
from e2b import Sandbox


def cleanup_sandboxes():
    load_dotenv()
    api_key = os.getenv("E2B_API_KEY")
    if not api_key:
        print("❌ E2B_API_KEY not found in environment.")
        return

    print("🔍 Fetching active sandboxes...")
    try:
        # In e2b 2.x, Sandbox.list() returns a paginator
        paginator = Sandbox.list()

        # Get the first page of items
        items = paginator.next_items()

        count = 0
        for sb in items:
            count += 1
            print(f"Killing sandbox {count}: {sb.sandbox_id} ({sb.template_id})")
            try:
                # We must use the static method with the sandbox_id because the
                # SandboxInfo object returned from list() doesn't have kill() method.
                Sandbox.kill(sb.sandbox_id)
                print(f"✅ Killed {sb.sandbox_id}")
            except Exception as e:
                print(f"⚠️ Could not kill {sb.sandbox_id}: {e}")

        if count == 0:
            print("✅ No active sandboxes found.")

    except Exception as e:
        print(f"❌ Error listing sandboxes: {e}")


if __name__ == "__main__":
    cleanup_sandboxes()
