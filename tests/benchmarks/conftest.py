import sys
from unittest.mock import MagicMock

for _mod in ["chromadb", "chromadb.api", "chromadb.api.client", "chromadb.api.types",
             "chromadb.config", "chromadb.errors", "chromadb.utils",
             "sentence_transformers", "sentence_transformers.SentenceTransformer"]:
    sys.modules[_mod] = MagicMock()
