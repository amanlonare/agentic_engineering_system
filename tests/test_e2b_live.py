import asyncio

import pytest
from e2b import Sandbox

from src.core.config import settings


@pytest.mark.asyncio
async def test_e2b_live():
    print("Testing live E2B sandbox spawning...")

    # Check if key is loaded
    api_key = settings.E2B_API_KEY
    if not api_key:
        print(
            "❌ Error: E2B_API_KEY not found in settings. Make sure it's in your .env file."
        )
        return

    print(f"🔑 E2B_API_KEY found (length: {len(api_key)})")

    try:
        print("🌐 Spawning sandbox...")
        # Note: We use Sandbox.create() as verified in previous steps
        with Sandbox.create(template="base", api_key=api_key) as sb:
            print(f"✅ Sandbox spawned! ID: {sb.sandbox_id}")

            # Check environment inside sandbox
            print("🔍 Checking environment inside sandbox...")
            res = sb.commands.run("env | grep _API_KEY || echo 'No keys found'")
            print(f"Sandbox Env Output:\n{res.stdout}")

            print("🚀 Testing command execution...")
            res = sb.commands.run("echo 'Hello from E2B!'")
            if res.exit_code == 0:
                print(f"✅ Command success: {res.stdout.strip()}")
            else:
                print(f"❌ Command failed: {res.stderr}")

    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    asyncio.run(test_e2b_live())
