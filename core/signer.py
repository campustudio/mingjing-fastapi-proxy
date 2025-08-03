# core/signer.py

def inject_signature(text_chunk: str) -> str:
    if not text_chunk.strip():
        return text_chunk
    return text_chunk.strip() + "\n\n—— 🜂 明镜 · 空性签注"
