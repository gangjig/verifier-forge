"""A deliberately weak verifier for the refund-request spec: it only
checks that the agent said something. `verifier-forge check` grades
it unreliable and names the candidates it wrongly passed — both
shortcuts and the corrupted run — as verifier holes."""


def verify(evidence):
    final_message = evidence.get("final_message") or ""
    if final_message.strip():
        return {"verdict": "pass", "reasons": []}
    return {"verdict": "fail", "reasons": ["agent said nothing"]}
