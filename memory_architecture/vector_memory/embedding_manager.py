from dotenv import load_dotenv
from openai import AzureOpenAI

import os


# ==========================================
# LOAD ENV VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# AZURE OPENAI CLIENT
# ==========================================

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv(
        "AZURE_OPENAI_EMBEDDING_API_VERSION"
    ),
    azure_endpoint=os.getenv(
        "AZURE_OPENAI_ENDPOINT"
    ),
    timeout=180,
    max_retries=5
)


# ==========================================
# EMBEDDING MANAGER
# ==========================================

class EmbeddingManager:

    def __init__(self):

        self.embedding_model = os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        )

    def generate_embedding(
        self,
        text: str
    ):

        try:

            response = client.embeddings.create(
                model=self.embedding_model,
                input=text
            )

            embedding = (
                response.data[0].embedding
            )

            return embedding

        except Exception as e:

            print(
                f"\n❌ Embedding generation failed: {str(e)}\n"
            )

            return None