
import os

from dotenv import load_dotenv

load_dotenv()

print("\n🔥 DETECTING AVAILABLE AI MODELS...\n")


# ==========================================
# OPENAI MODELS
# ==========================================

def detect_openai_models():

    print("\n==============================")
    print(" OPENAI MODELS ")
    print("==============================")

    try:

        from openai import OpenAI

        client = OpenAI(

            api_key=os.getenv(
                "OPENAI_API_KEY"
            )
        )

        models = client.models.list()

        for model in models.data:

            print(f"✅ {model.id}")

    except Exception as error:

        print(f"❌ OPENAI ERROR:\n{error}")


# ==========================================
# GEMINI MODELS
# ==========================================

def detect_gemini_models():

    print("\n==============================")
    print(" GEMINI MODELS ")
    print("==============================")

    try:

        import google.generativeai as genai

        genai.configure(

            api_key=os.getenv(
                "GEMINI_API_KEY"
            )
        )

        models = genai.list_models()

        for model in models:

            print(f"✅ {model.name}")

    except Exception as error:

        print(f"❌ GEMINI ERROR:\n{error}")


# ==========================================
# AZURE OPENAI
# ==========================================

def detect_azure_models():

    print("\n==============================")
    print(" AZURE OPENAI ")
    print("==============================")

    try:

        endpoint = os.getenv(
            "AZURE_OPENAI_ENDPOINT"
        )

        deployment = os.getenv(
            "AZURE_OPENAI_DEPLOYMENT"
        )

        print(f"✅ Endpoint: {endpoint}")

        print(f"✅ Deployment: {deployment}")

        print(
            "\n⚠️ Azure does NOT expose model listing API."
        )

        print(
            "You must know deployment names manually."
        )

    except Exception as error:

        print(f"❌ AZURE ERROR:\n{error}")


# ==========================================
# RUN
# ==========================================

detect_openai_models()

detect_gemini_models()

detect_azure_models()

print("\n🔥 MODEL DETECTION COMPLETE\n")