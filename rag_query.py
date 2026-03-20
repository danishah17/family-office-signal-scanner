import os

import anthropic
import chromadb
import openai
import requests
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

OPENAI_EMBED_MODEL = "text-embedding-3-small"
LOCAL_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "family_offices"
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))
ANTHROPIC_TIMEOUT = int(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "90"))
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "120"))


SYSTEM_PROMPT_RAG = """You are a family office intelligence analyst.
You have access to a curated database of family offices worldwide.

Answer questions based ONLY on the provided context (the retrieved records below).
Be specific — mention actual family office names, locations, and details from the data.

If you cannot find relevant records, say exactly:
"I found X records in the database but none closely match this query. The closest matches are: [list them]"
(Replace X with the number of records in the database given in the user message.)
Never make up family office names not in the context.

If the data doesn't contain enough information to answer fully, say so honestly and share what IS available.

Format your response clearly with:
- A direct answer to the question
- Specific family offices that match (with names), when the context supports it
- Any relevant caveats about data completeness
"""


def check_openai_embeddings_working(client: openai.OpenAI) -> bool:
    try:
        client.with_options(timeout=OPENAI_TIMEOUT).embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input="embedding connectivity check",
        )
        return True
    except Exception as exc:
        print(
            f"[RAG QUERY] OpenAI embedding probe failed ({exc!r}) — "
            "using explicit local fallback."
        )
        return False


class FamilyOfficeRAG:
    def __init__(self):
        self.chroma_path = CHROMA_PATH
        self.collection_name = COLLECTION_NAME
        self.client = None
        self.collection = None
        self._init_error = None
        self.openai_client = None
        self.anthropic_client = None
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.mistral_api_key = os.getenv("MISTRAL_API_KEY", "").strip()
        self.mistral_chat_model = os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.openai_timeout = OPENAI_TIMEOUT
        self.anthropic_timeout = ANTHROPIC_TIMEOUT
        self.gemini_timeout = GEMINI_TIMEOUT
        self.local_embedder = None
        self._use_openai_embeddings = False
        self.embedding_provider_label = "uninitialized"

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)

        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)

        self._resolve_embedding_provider()

        try:
            self.client = chromadb.PersistentClient(path=self.chroma_path)
            names = [c.name for c in self.client.list_collections()]
            if COLLECTION_NAME not in names:
                self._init_error = (
                    f"Collection '{COLLECTION_NAME}' not found under {self.chroma_path}. "
                    "Run rag_ingest.py first."
                )
            else:
                self.collection = self.client.get_collection(COLLECTION_NAME)
                if self.collection.count() == 0:
                    self._init_error = (
                        "Collection exists but has 0 documents. Run rag_ingest.py first."
                    )
        except Exception as exc:
            self._init_error = str(exc)
            self.collection = None

    def _get_local_embedder(self):
        if self.local_embedder is None:
            self.local_embedder = SentenceTransformer(LOCAL_EMBED_MODEL)
        return self.local_embedder

    def _resolve_embedding_provider(self):
        """Match rag_ingest.py: OpenAI text-embedding-3-small if key valid, else local (explicit)."""
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            self._use_openai_embeddings = False
            self.embedding_provider_label = f"explicit fallback: {LOCAL_EMBED_MODEL}"
            print(f"[RAG QUERY] OPENAI_API_KEY not set → {self.embedding_provider_label}")
            return

        if self.openai_client is None:
            self._use_openai_embeddings = False
            self.embedding_provider_label = f"explicit fallback: {LOCAL_EMBED_MODEL}"
            print("[RAG QUERY] OpenAI client missing → " + self.embedding_provider_label)
            return

        if check_openai_embeddings_working(self.openai_client):
            self._use_openai_embeddings = True
            self.embedding_provider_label = f"OpenAI ({OPENAI_EMBED_MODEL})"
            print(f"[RAG QUERY] Embedding provider: {self.embedding_provider_label}")
            return

        self._use_openai_embeddings = False
        self.embedding_provider_label = f"explicit fallback: {LOCAL_EMBED_MODEL}"
        print(
            f"[RAG QUERY] OpenAI unavailable → {self.embedding_provider_label} "
            "(must match ingest embedding model for quality)."
        )

    def is_database_ready(self) -> bool:
        if self.collection is None:
            return False
        try:
            return self.collection.count() > 0
        except Exception:
            return False

    def database_count(self) -> int:
        if self.collection is None:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    def init_status_message(self) -> str:
        if self._init_error:
            return self._init_error
        if not self.is_database_ready():
            return "Database empty or missing — run rag_ingest.py first."
        return ""

    def get_embedding(self, text: str):
        if self._use_openai_embeddings and self.openai_client is not None:
            response = self.openai_client.with_options(timeout=self.openai_timeout).embeddings.create(
                model=OPENAI_EMBED_MODEL,
                input=text,
            )
            return response.data[0].embedding
        model = self._get_local_embedder()
        return model.encode(text).tolist()

    def _answer_with_openai(self, system_prompt, user_prompt):
        response = self.openai_client.with_options(timeout=self.openai_timeout).chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.1,
        )
        return response.choices[0].message.content

    def _answer_with_anthropic(self, system_prompt, user_prompt):
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        response = self.anthropic_client.with_options(timeout=self.anthropic_timeout).messages.create(
            model=model,
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        for block in response.content:
            if getattr(block, "type", "") == "text":
                text += block.text
        return text.strip()

    def _answer_with_gemini(self, system_prompt, user_prompt):
        if not self.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY missing")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
        }
        resp = requests.post(
            f"{url}?key={self.gemini_api_key}",
            json=payload,
            timeout=self.gemini_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("No Gemini candidates in response")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not text:
            raise RuntimeError("Empty Gemini response")
        return text

    def _answer_with_mistral(self, system_prompt, user_prompt):
        if not self.mistral_api_key:
            raise RuntimeError("MISTRAL_API_KEY missing")
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.mistral_chat_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 800,
            },
            timeout=self.gemini_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No Mistral choices in response")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise RuntimeError("Empty Mistral response")
        return content

    def _answer_retrieval_only(self, user_question, sources, db_count: int):
        lines = [
            f"Direct answer unavailable from LLM backend. Database has {db_count} records.",
            f"Retrieved {len(sources)} matching rows for: {user_question}",
            "",
        ]
        for i, s in enumerate(sources, 1):
            lines.append(
                f"{i}. {s.get('fo_name','Unknown')} | {s.get('country','')} | "
                f"Relevance: {s.get('relevance','')}% | {s.get('website','')}"
            )
        lines.append("")
        lines.append("Use these sources as the evidence set for the query.")
        return "\n".join(lines)

    def query(self, user_question, n_results=5):
        db_count = self.database_count()

        if self.collection is None:
            return {
                "answer": (
                    "Database not initialized. Run `python rag_ingest.py` after "
                    "`output/family_office_intelligence_master.csv` exists."
                ),
                "sources": [],
                "records_searched": 0,
                "records_retrieved": 0,
                "error": self._init_error or "no_collection",
            }

        if db_count == 0:
            return {
                "answer": (
                    "The database has no indexed records. Run `python rag_ingest.py` "
                    "to build the Chroma index from the master CSV."
                ),
                "sources": [],
                "records_searched": 0,
                "records_retrieved": 0,
                "error": "empty_database",
            }

        query_embedding = self.get_embedding(user_question)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        if not docs:
            return {
                "answer": (
                    f"I found {db_count} records in the database but retrieval returned no chunks. "
                    "Try re-running ingestion or broadening your query."
                ),
                "sources": [],
                "records_searched": db_count,
                "records_retrieved": 0,
                "weak_match": True,
            }

        context_parts = []
        sources = []

        for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
            relevance = round((1 - float(dist)) * 100, 1)
            context_parts.append(f"Record {i+1} (Relevance: {relevance}%):\n{doc}")
            sources.append(
                {
                    "fo_name": meta.get("fo_name", "Unknown"),
                    "website": meta.get("website", ""),
                    "country": meta.get("hq_country", ""),
                    "relevance": relevance,
                }
            )

        # Low relevance: still list "closest" but flag for UI
        best_rel = sources[0]["relevance"] if sources else 0.0
        weak_match = best_rel < 35.0

        context = "\n\n---\n\n".join(context_parts)

        system_prompt = SYSTEM_PROMPT_RAG

        user_prompt = f"""
Total records in database: {db_count}
Question: {user_question}

Retrieved Family Office Records:
{context}

Please answer based on these records only. Do not invent names.
"""

        try:
            answer = self._answer_with_anthropic(system_prompt, user_prompt)
        except Exception:
            try:
                answer = self._answer_with_openai(system_prompt, user_prompt)
            except Exception:
                try:
                    answer = self._answer_with_gemini(system_prompt, user_prompt)
                except Exception:
                    try:
                        answer = self._answer_with_mistral(system_prompt, user_prompt)
                    except Exception:
                        answer = self._answer_retrieval_only(user_question, sources, db_count)

        out = {
            "answer": answer,
            "sources": sources,
            "records_searched": db_count,
            "records_retrieved": len(sources),
            "weak_match": weak_match,
        }
        if weak_match and sources:
            out["suggested_queries"] = [
                "Show me family offices in North America",
                "Which family offices list an email for a decision maker?",
                "Family offices with geographic focus in Europe",
            ]
        return out
