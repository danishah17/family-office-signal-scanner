import json
import os
import time

import anthropic
import openai
import requests
from dotenv import load_dotenv

load_dotenv()


def result(name, ok, detail, elapsed):
    return {
        "provider": name,
        "ok": ok,
        "detail": detail,
        "elapsed_ms": int(elapsed * 1000),
    }


def test_anthropic():
    start = time.time()
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return result("anthropic", False, "ANTHROPIC_API_KEY missing", time.time() - start)
    try:
        client = anthropic.Anthropic(api_key=key)
        models = [m.id for m in client.models.list(limit=5).data]
        resp = client.with_options(timeout=45).messages.create(
            model=models[0],
            max_tokens=20,
            messages=[{"role": "user", "content": "Reply exactly: ok"}],
        )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        ).strip()
        return result("anthropic", True, f"model={models[0]} response={text[:40]}", time.time() - start)
    except Exception as e:
        return result("anthropic", False, str(e), time.time() - start)


def test_openai():
    start = time.time()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return result("openai", False, "OPENAI_API_KEY missing", time.time() - start)
    try:
        client = openai.OpenAI(api_key=key)
        emb = client.with_options(timeout=30).embeddings.create(
            model="text-embedding-3-small",
            input="test embedding",
        )
        dim = len(emb.data[0].embedding)
        chat = client.with_options(timeout=30).chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Reply exactly: ok"}],
            max_tokens=10,
        )
        text = (chat.choices[0].message.content or "").strip()
        return result("openai", True, f"embed_dim={dim} chat={text[:30]}", time.time() - start)
    except Exception as e:
        return result("openai", False, str(e), time.time() - start)


def test_gemini():
    start = time.time()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if not key:
        return result("gemini", False, "GEMINI_API_KEY missing", time.time() - start)
    try:
        emb_url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
        emb_payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": "test embedding"}]},
        }
        emb_resp = requests.post(f"{emb_url}?key={key}", json=emb_payload, timeout=45)
        emb_resp.raise_for_status()
        emb_vals = emb_resp.json().get("embedding", {}).get("values", [])
        dim = len(emb_vals)

        gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        gen_payload = {"contents": [{"parts": [{"text": "Reply exactly: ok"}]}]}
        gen_resp = requests.post(f"{gen_url}?key={key}", json=gen_payload, timeout=60)
        gen_resp.raise_for_status()
        data = gen_resp.json()
        cands = data.get("candidates", [])
        if not cands:
            raise RuntimeError("No candidates in Gemini response")
        text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
        return result("gemini", True, f"embed_dim={dim} chat={text[:30]}", time.time() - start)
    except Exception as e:
        return result("gemini", False, str(e), time.time() - start)


def test_mistral():
    start = time.time()
    key = os.getenv("MISTRAL_API_KEY", "").strip()
    embed_model = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")
    chat_model = os.getenv("MISTRAL_CHAT_MODEL", "mistral-small-latest")
    if not key:
        return result("mistral", False, "MISTRAL_API_KEY missing", time.time() - start)
    try:
        emb_resp = requests.post(
            "https://api.mistral.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": embed_model, "input": ["test embedding"]},
            timeout=45,
        )
        emb_resp.raise_for_status()
        emb_data = emb_resp.json()
        dim = len(((emb_data.get("data") or [{}])[0]).get("embedding", []))

        chat_resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": chat_model,
                "messages": [{"role": "user", "content": "Reply exactly: ok"}],
                "max_tokens": 20,
                "temperature": 0.1,
            },
            timeout=45,
        )
        chat_resp.raise_for_status()
        chat_data = chat_resp.json()
        text = (((chat_data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")
        return result("mistral", True, f"embed_dim={dim} chat={str(text)[:30]}", time.time() - start)
    except Exception as e:
        return result("mistral", False, str(e), time.time() - start)


def main():
    checks = [test_anthropic(), test_openai(), test_gemini(), test_mistral()]
    print(json.dumps(checks, indent=2))
    ok = [c["provider"] for c in checks if c["ok"]]
    print("\nUsable providers:", ", ".join(ok) if ok else "none")


if __name__ == "__main__":
    main()
