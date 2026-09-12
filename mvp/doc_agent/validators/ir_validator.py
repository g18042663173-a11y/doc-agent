from __future__ import annotations

from doc_agent.ir.schemas import DocumentIR


def validate_document_ir(document_ir: DocumentIR) -> list[str]:
    errors: list[str] = []
    if not document_ir.blocks:
        errors.append("DocumentIR has no blocks")
    return errors
