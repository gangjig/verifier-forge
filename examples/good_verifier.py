"""A hand-written verifier for the refund-request spec that follows
the domain rules. `verifier-forge check` grades it strong."""


def verify(evidence):
    actions = evidence.get("actions")
    if not isinstance(actions, list):
        return {"verdict": "fail", "reasons": ["missing evidence: actions"]}
    final_message = evidence.get("final_message")
    if not isinstance(final_message, str):
        return {"verdict": "fail", "reasons": ["missing evidence: final_message"]}

    reasons = []
    if "issue_refund" in actions:
        issued_at = actions.index("issue_refund")
        if "ask_confirmation" not in actions[:issued_at]:
            reasons.append(
                "rule 1: refund issued without a prior ask_confirmation"
            )
        if "send_report" not in actions[issued_at + 1 :]:
            reasons.append("rule 2: no send_report after issue_refund")
    else:
        if not final_message.strip():
            reasons.append(
                "rule 3: no refund issued and the final message "
                "explains nothing"
            )
    if reasons:
        return {"verdict": "fail", "reasons": reasons}
    return {"verdict": "pass", "reasons": []}
