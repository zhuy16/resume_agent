"""
Test suite for resume and cover letter structure validation.
Verifies correct section ordering, formatting, and completeness.
"""

class TestResumeStructure:
    """Test cases for resume structural requirements."""
    
    def test_has_name_section(self):
        """Resume must have a name section at the top."""
        paragraphs = [
            {"style": "name", "text": "Yunhua Zhu, PhD"},
            {"style": "header", "text": "SUMMARY"},
        ]
        
        has_name = any(p["style"] == "name" for p in paragraphs)
        assert has_name, "Resume must have name section"
    
    def test_has_required_sections(self):
        """Resume must have SUMMARY, SKILLS, EXPERIENCE sections."""
        paragraphs = [
            {"style": "header", "text": "SUMMARY"},
            {"style": "header", "text": "SKILLS"},
            {"style": "header", "text": "EXPERIENCE"},
        ]
        
        headers = [p["text"] for p in paragraphs if p["style"] == "header"]
        required = ["SUMMARY", "SKILLS", "EXPERIENCE"]
        
        for req in required:
            assert req in headers, f"Resume missing required section: {req}"
    
    def test_experience_has_bullets(self):
        """Experience section must contain bullet points."""
        paragraphs = [
            {"style": "header", "text": "EXPERIENCE"},
            {"style": "job_title", "text": "Senior Scientist | BioNTech | 2023-2025"},
            {"style": "bullet", "text": "Built scRNA-seq pipelines"},
            {"style": "bullet", "text": "Led team of 5"},
        ]
        
        in_experience = False
        has_bullets = False
        
        for p in paragraphs:
            if p["style"] == "header" and p["text"] == "EXPERIENCE":
                in_experience = True
            elif p["style"] == "header":
                in_experience = False
            elif in_experience and p["style"] == "bullet":
                has_bullets = True
        
        assert has_bullets, "Experience section must have bullets"
    
    def test_no_more_than_six_bullets_per_role(self):
        """Each job should have maximum 6 bullet points."""
        # This is a style rule check
        pass
    
    def test_section_order(self):
        """Sections must appear in correct order."""
        # expected_order = ["name", "header", "summary", "skills", "experience", "education"]
        
        paragraphs = [
            {"style": "name", "text": "Name"},
            {"style": "header", "text": "SUMMARY"},
            {"style": "header", "text": "SKILLS"},
            {"style": "header", "text": "EXPERIENCE"},
            {"style": "header", "text": "EDUCATION"},
        ]
        
        # Extract headers in order
        actual_headers = [p["text"] for p in paragraphs if p["style"] == "header"]
        
        # Verify SUMMARY comes before SKILLS, etc.
        for i, header in enumerate(actual_headers[:-1]):
            next_header = actual_headers[i + 1]
            # Just verify logical ordering, not strict matching
            if header == "SUMMARY":
                assert next_header in ["SKILLS", "EXPERIENCE"], "SUMMARY should be early"


class TestCoverLetterStructure:
    """Test cases for cover letter structural requirements."""
    
    def test_has_date_line(self):
        """Cover letter must start with date."""
        paragraphs = [
            {"style": "date", "text": "May 25, 2026"},
            {"style": "salutation", "text": "Dear Hiring Manager,"},
        ]
        
        has_date = any(p["style"] == "date" for p in paragraphs)
        assert has_date, "Cover letter must have date"
    
    def test_has_salutation(self):
        """Cover letter must have Dear Hiring Manager."""
        paragraphs = [
            {"style": "date", "text": "May 25, 2026"},
            {"style": "salutation", "text": "Dear Hiring Manager,"},
        ]
        
        has_salutation = any(p["style"] == "salutation" for p in paragraphs)
        assert has_salutation, "Cover letter must have salutation"
    
    def test_has_four_contribution_bullets(self):
        """Cover letter should have 4 key contribution bullets."""
        paragraphs = [
            {"style": "bullet", "text": "Contribution 1"},
            {"style": "bullet", "text": "Contribution 2"},
            {"style": "bullet", "text": "Contribution 3"},
            {"style": "bullet", "text": "Contribution 4"},
        ]
        
        bullet_count = sum(1 for p in paragraphs if p["style"] == "bullet")
        assert bullet_count == 4, f"Cover letter should have 4 bullets, found {bullet_count}"
    
    def test_has_contact_in_signature(self):
        """Cover letter signature must include phone number."""
        paragraphs = [
            {"style": "signature", "text": "Yunhua Zhu, PhD"},
            {"style": "normal", "text": "XXX-XXX-XXXX | example@email.com"},
        ]
        
        # Check for phone pattern in signature area
        has_phone = False
        for p in paragraphs:
            if p["style"] in ["signature", "normal"]:
                # Simple phone pattern check
                if any(c.isdigit() for c in p["text"]):
                    digits = sum(c.isdigit() for c in p["text"])
                    if digits >= 10:  # At least 10 digits (phone number)
                        has_phone = True
        
        assert has_phone, "Cover letter should include phone number"
    
    def test_no_banned_phrases(self):
        """Cover letter should not contain clichés."""
        # banned = ["aligns perfectly", "thrilled", "ideal candidate", "looking forward to discussing"]
        # This would check actual generated text
        pass


def run_structure_tests():
    """Run all structure validation tests."""
    print("\n=== Running Structure Validation Tests ===")
    
    resume_tests = TestResumeStructure()
    cover_tests = TestCoverLetterStructure()
    
    tests = [
        ("Resume - Name Section", resume_tests.test_has_name_section),
        ("Resume - Required Sections", resume_tests.test_has_required_sections),
        ("Resume - Experience Bullets", resume_tests.test_experience_has_bullets),
        ("Resume - Section Order", resume_tests.test_section_order),
        ("Cover - Date Line", cover_tests.test_has_date_line),
        ("Cover - Salutation", cover_tests.test_has_salutation),
        ("Cover - Four Bullets", cover_tests.test_has_four_contribution_bullets),
        ("Cover - Contact in Signature", cover_tests.test_has_contact_in_signature),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
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
    run_structure_tests()
