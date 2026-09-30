"""Prompt engineering and context formatting for project-aware conversational Q&A."""

from backend.app.models.conversation import Message
from backend.app.retrieval.models import EvidenceChunk

SYSTEM_PROMPT = """You are an expert AI codebase analyst. Your role is to answer questions
about the codebase strictly and truthfully based ONLY on the provided code evidence.

STRICT RULES:
1. Grounding: Answer ONLY from the provided code evidence snippets. Do not assume or
   extrapolate beyond what is shown in the code.
2. Insufficient Evidence: If the provided evidence does not contain sufficient information
   to answer the question with certainty, you MUST clearly state:
   "The provided codebase evidence does not contain sufficient information to answer this question."
   Do not guess or extrapolate.
3. Citations: Every statement about functionality, functions, classes, or architecture MUST
   cite the exact source file and line range in the format `[file_path:start_line-end_line]`
   (e.g. `[src/auth.py:10-25]`).
4. No Hallucinations: NEVER invent files, functions, classes, methods, or endpoints that
   are not in the provided evidence.
5. Symbols: Reference exact symbol names (function names, class names, variables) as they
   appear in the snippets."""


def format_evidence_block(evidence: list[EvidenceChunk]) -> str:
    """Format retrieved code chunks into a structured evidence block."""
    if not evidence:
        return "No relevant code snippets were found in the project codebase."

    lines = ["--- CODE EVIDENCE ---"]
    for idx, chunk in enumerate(evidence, 1):
        lang = chunk.metadata.get("language", "")
        symbol_info = f"Symbol: {chunk.symbol}" if chunk.symbol else "Symbol: N/A"
        lines.append(f"Snippet {idx}:")
        lines.append(f"File: {chunk.file_path} (Lines {chunk.start_line}-{chunk.end_line})")
        lines.append(symbol_info)
        lines.append("Content:")
        lines.append(f"```{lang}")
        lines.append(chunk.chunk_content)
        lines.append("```\n")

    lines.append("---------------------")
    return "\n".join(lines)


def build_chat_messages(
    history: list[Message],
    evidence: list[EvidenceChunk],
    user_question: str,
    max_history_turns: int = 10,
) -> list[dict[str, str]]:
    """Assemble the complete prompt message list for the LLM provider."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # Append recent conversation history (excluding the current turn)
    recent_history = history[-max_history_turns:] if history else []
    for msg in recent_history:
        if msg.role in ("user", "assistant"):
            messages.append({"role": msg.role, "content": msg.content})

    # Format the latest turn with retrieved code evidence
    evidence_block = format_evidence_block(evidence)
    current_content = f"{evidence_block}\n\nUser Question: {user_question}"

    messages.append({"role": "user", "content": current_content})
    return messages
