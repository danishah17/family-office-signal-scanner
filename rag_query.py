import os

import chromadb
import openai
from dotenv import load_dotenv

load_dotenv()


class FamilyOfficeRAG:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_collection("family_offices")
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def get_embedding(self, text):
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def query(self, user_question, n_results=5):
        # Step 1: Embed the user question
        query_embedding = self.get_embedding(user_question)

        # Step 2: Retrieve top-k relevant records from ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        # Step 3: Build context from retrieved records
        context_parts = []
        sources = []

        for i, (doc, meta, dist) in enumerate(
            zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ):
            relevance = round((1 - dist) * 100, 1)
            context_parts.append(f"Record {i+1} (Relevance: {relevance}%):\n{doc}")
            sources.append(
                {
                    "fo_name": meta.get("fo_name", "Unknown"),
                    "website": meta.get("website", ""),
                    "country": meta.get("hq_country", ""),
                    "relevance": relevance,
                }
            )

        context = "\n\n---\n\n".join(context_parts)

        # Step 4: Generate answer using GPT-4o-mini
        system_prompt = """You are a family office intelligence analyst. 
        You have access to a curated database of family offices worldwide.
        
        Answer questions based ONLY on the provided context.
        Be specific — mention actual family office names, locations, 
        and details from the data.
        
        If the data doesn't contain enough information to answer fully,
        say so honestly and share what IS available.
        
        Format your response clearly with:
        - A direct answer to the question
        - Specific family offices that match (with names)
        - Any relevant caveats about data completeness
        """

        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"""
                Question: {user_question}
                
                Retrieved Family Office Records:
                {context}
                
                Please answer based on these records.
                """,
                },
            ],
            max_tokens=800,
            temperature=0.1,
        )

        answer = response.choices[0].message.content

        return {
            "answer": answer,
            "sources": sources,
            "records_searched": self.collection.count(),
            "records_retrieved": len(sources),
        }
