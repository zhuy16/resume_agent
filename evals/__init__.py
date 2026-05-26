"""Evaluation framework for resume generation quality."""

# Delay imports to avoid heavy dependencies at module level
def run_hallucination_tests():
    from evals.test_hallucination import run_hallucination_tests as _run
    return _run()

def run_structure_tests():
    from evals.test_structure import run_structure_tests as _run
    return _run()

__all__ = [
    "run_hallucination_tests",
    "run_structure_tests",
]
