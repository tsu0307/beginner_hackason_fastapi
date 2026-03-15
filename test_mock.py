import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.append(str(backend_dir))

from app.services.llm_gateway import call_llm

def test_mock_mode():
    print("Testing Mock Mode...")
    os.environ["MOCK_MODE"] = "true"
    
    system = "分岐生成"
    user = "テストユーザー"
    
    print(f"Calling LLM with system='{system}' and user='{user}'")
    response = call_llm("gemini", system, user)
    print("\nResponse:")
    print(response)
    
    if "branches" in response:
        print("\nSUCCESS: Received mock branches response.")
    else:
        print("\nFAILURE: Did not receive expected mock response.")

if __name__ == "__main__":
    test_mock_mode()
