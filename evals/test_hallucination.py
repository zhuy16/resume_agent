"""
Test suite for hallucination detection in generated resumes.
Verifies that no facts are invented beyond what's in the source resume.
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    pytest = None


class TestHallucinationDetection:
    """Test cases for verifying factual accuracy."""
    
    def __init__(self):
        self._validator = None
    
    @property
    def validator(self):
        """Lazy-load validator agent."""
        if self._validator is None:
            from agents.validator_agent import ValidatorAgent
            from services.llm_client import LLMClient
            self._validator = ValidatorAgent(llm_client=LLMClient())
        return self._validator
    
    def test_no_fabricated_companies(self, validator=None):
        """Generated resume should not mention companies not in source."""
        validator = validator or self.validator
        source = """
        Senior Scientist | BioNTech | 2023-2025
        - Built scRNA-seq pipelines
        """
        draft = """
        Senior Scientist | BioNTech | 2023-2025
        - Built scRNA-seq pipelines at Google
        """
        
        violations = validator.validate_claims(draft, source)
        company_violations = [v for v in violations if "google" in v["issue"].lower()]
        assert len(company_violations) > 0, "Should flag fabricated company"
    
    def test_no_inflated_titles(self, validator=None):
        """Generated resume should not claim higher titles than source."""
        validator = validator or self.validator
        source = """
        Senior Scientist | BioNTech | 2023-2025
        """
        draft = """
        Principal Scientist | BioNTech | 2023-2025
        """
        
        violations = validator.validate_claims(draft, source)
        title_violations = [v for v in violations if "principal" in v["issue"].lower()]
        assert len(title_violations) > 0, "Should flag title inflation"
    
    def test_no_fabricated_metrics(self, validator=None):
        """Generated resume should not invent metrics not in source."""
        validator = validator or self.validator
        source = """
        - Reduced analysis time
        """
        draft = """
        - Reduced analysis time by 95%
        """
        
        violations = validator.validate_claims(draft, source)
        metric_violations = [v for v in violations if "95" in v["issue"]]
        assert len(metric_violations) > 0, "Should flag invented metric"
    
    def test_portfolio_not_attributed_to_company(self, validator=None):
        """Portfolio projects should not appear as company work."""
        validator = validator or self.validator
        source = """
        ## Portfolio Projects
        - linkedin-job-scout: Personal project using Claude API
        
        ## Experience
        Senior Scientist | BioNTech | 2023-2025
        - Built scRNA-seq pipelines
        """
        draft = """
        ## Experience
        Senior Scientist | BioNTech | 2023-2025
        - Designed linkedin-job-scout using Claude API
        """
        
        violations = validator.validate_claims(draft, source)
        attribution_violations = [v for v in violations if "portfolio" in v["issue"].lower()]
        assert len(attribution_violations) > 0, "Should flag portfolio attribution to company"


def run_hallucination_tests():
    """Run all hallucination detection tests."""
    from agents.validator_agent import ValidatorAgent
    from services.llm_client import LLMClient
    
    print("\n=== Running Hallucination Detection Tests ===")
    
    # Manual test runner (since we may not have pytest in env)
    validator = ValidatorAgent(llm_client=LLMClient())
    test_suite = TestHallucinationDetection()
    
    tests = [
        ("Fabricated Companies", test_suite.test_no_fabricated_companies),
        ("Inflated Titles", test_suite.test_no_inflated_titles),
        ("Fabricated Metrics", test_suite.test_no_fabricated_metrics),
        ("Portfolio Attribution", test_suite.test_portfolio_not_attributed_to_company),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func(validator)
            print(f"  ✅ {name}: PASSED")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: FAILED - {e}")
            failed += 1
        except Exception as e:
            print(f"  ⚠️  {name}: ERROR - {e}")
            failed += 1
    
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    run_hallucination_tests()
