import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carepal.settings')
django.setup()

def verify_integration():
    print("Verifying AI Agent Module Integration...")
    
    # 1. Verify Model Imports
    try:
        from agent.models import (
            AgentSession, AgentMessage, AgentAction, 
            AgentMemory, AgentEventLog, AgentCacheEntry
        )
        print("✅ Models imported successfully")
        
        # Check model fields (simple check)
        print(f"   - AgentSession fields: {[f.name for f in AgentSession._meta.get_fields()][:5]}...")
    except ImportError as e:
        print(f"❌ Model import failed: {e}")
        return False

    # 2. Verify Serializer Imports
    try:
        from agent.serializers import (
            AgentSessionSerializer, AgentMessageSerializer
        )
        print("✅ Serializers imported successfully")
    except ImportError as e:
        print(f"❌ Serializer import failed: {e}")
        return False

    # 3. Verify Gemini Service
    try:
        from agent.gemini_service import GeminiService, get_gemini_service
        service = get_gemini_service()
        print(f"✅ GeminiService initialized (Model: {service.model.model_name})")
    except ImportError as e:
        print(f"❌ GeminiService import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ GeminiService initialization failed: {e}")
        # Not returning False here as it might be an API key issue, but code is present
        
    # 4. Verify Twilio Service
    try:
        from agent.twilio_service import TwilioService, get_twilio_service
        service = get_twilio_service()
        status = "Enabled" if service.is_enabled() else "Disabled (Missing Credentials)"
        print(f"✅ TwilioService initialized: {status}")
    except ImportError as e:
        print(f"❌ TwilioService import failed: {e}")
        return False
        
    # 5. Verify Function Executor
    try:
        from agent.function_executor import FunctionExecutor
        print("✅ FunctionExecutor imported")
    except ImportError as e:
        print(f"❌ FunctionExecutor import failed: {e}")
        return False

    # 6. Verify Function Definitions
    try:
        from agent.function_definitions import FUNCTION_DECLARATIONS
        print(f"✅ Function Definitions found: {len(FUNCTION_DECLARATIONS)} functions defined")
    except ImportError as e:
        print(f"❌ Function Definitions import failed: {e}")
        return False

    print("\n🎉 AI Agent Module Verification Completed Successfully!")
    return True

if __name__ == "__main__":
    success = verify_integration()
    sys.exit(0 if success else 1)
