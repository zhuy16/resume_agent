"""
ValidatorAgent — cross-check every factual claim in the draft resume/cover letter
against the source resume text. Uses Claude Haiku for speed.
Flags violations; does NOT auto-correct (v1 behaviour).
"""
import anthropic

import config


_VALIDATOR_TOOL = {
    "name": "report_violations",
    "description": (
        "Report any factual claims in the draft that cannot be verified "
        "in the source resume."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "valid": {
                "type": "boolean",
                "description": "True if no violations found, False otherwise.",
            },
            "violations": {
                "type": "array",
                "description": "List of unverifiable claims found in the draft.",
                "items": {
                    "type": "object",
                    "properties": {
                        "draft_text": {
                            "type": "string",
                            "description": "The exact sentence or phrase from the draft.",
                        },
                        "issue": {
                            "type": "string",
                            "description": "Why this claim cannot be verified in the source resume.",
                        },
                    },
                    "required": ["draft_text", "issue"],
                },
            },
        },
        "required": ["valid", "violations"],
    },
}

_VALIDATOR_SYSTEM = """\
You are a strict resume fact-checker. You will be given:
1. A source resume — the ground truth of what the candidate has actually done.
2. A draft resume (and optionally a cover letter) — generated output to verify.

Your job: identify every claim in the draft that CANNOT be directly verified in the source resume.

A violation is any of:
  - A metric or number not present in the source (e.g. "improved speed by 40%" if source says nothing about speed)
  - A tool, skill, language, or technology not mentioned in the source
  - A job title, company, or date that differs from the source
  - An achievement, project, or responsibility not mentioned in the source
  - Any invented credential, publication, patent, or award

NOT a violation:
  - Rephrasing or reordering content that IS in the source
  - Minor grammatical changes that preserve meaning
  - Summary sentences that accurately synthesise source content
  - Education graduation years inferred from career timeline (e.g. PhD year from first job start)
  - Any content that appears in the SUPPLEMENTAL FACTS block below (portfolio patch, addenda)

Call the report_violations tool with your findings. Be precise — quote the exact draft text.\
"""


class ValidatorAgent:
    """
    Cross-check draft paragraphs against source resume text.
    Returns a validation report dict.
    """

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def run(
        self,
        resume_paragraphs: list[dict],
        cover_paragraphs: list[dict],
        source_text: str,
        supplemental_facts: str = "",
    ) -> dict:
        """
        Returns:
          {
            "valid":      bool,
            "violations": [{"draft_text": str, "issue": str}, ...],
          }
        """
        draft_resume = "\n".join(
            f"[{p['style']}] {p['text']}" for p in resume_paragraphs
        )
        draft_cover = "\n".join(
            f"[{p['style']}] {p['text']}" for p in cover_paragraphs
        ) if cover_paragraphs else ""

        draft_block = f"## Draft Resume\n{draft_resume}"
        if draft_cover:
            draft_block += f"\n\n## Draft Cover Letter\n{draft_cover}"

        supp_block = f"\n\n## Supplemental Facts (also ground truth — do NOT flag these)\n{supplemental_facts}" if supplemental_facts else ""
        user_msg = (
            f"## Source Resume (ground truth)\n{source_text}"
            f"{supp_block}\n\n"
            f"{draft_block}\n\n"
            "Check the draft carefully and call report_violations with your findings."
        )

        print("  Calling Claude Haiku (validation)...")
        response = self._client.messages.create(
            model=config.VALIDATOR_MODEL,
            max_tokens=2048,
            system=_VALIDATOR_SYSTEM,
            tools=[_VALIDATOR_TOOL],
            tool_choice={"type": "tool", "name": "report_violations"},
            messages=[{"role": "user", "content": user_msg}],
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "report_violations":
                result = {
                    "valid":      block.input.get("valid", True),
                    "violations": block.input.get("violations", []),
                }
                self._print_report(result)
                return result

        return {"valid": True, "violations": []}

    def _print_report(self, result: dict) -> None:
        if result["valid"]:
            print("  [validator] PASSED — no violations found.")
            return
        n = len(result["violations"])
        print(f"  [validator] WARNING — {n} violation(s) found:")
        for i, v in enumerate(result["violations"], 1):
            print(f"    {i}. \"{v['draft_text'][:80]}\"")
            print(f"       Issue: {v['issue']}")
