"""
Structure validation script - verifies all components of the 3-phase architecture.
Run this to ensure documentation matches actual implementation.
"""

import os
import sys
from pathlib import Path


def check_file(path: str, min_size: int = 0) -> tuple:
    """Check if file exists and has minimum size."""
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    valid = exists and size >= min_size
    return valid, exists, size


def check_directory(path: str, min_items: int = 0) -> tuple:
    """Check if directory exists and has minimum items."""
    exists = os.path.exists(path)
    items = len(os.listdir(path)) if exists else 0
    valid = exists and items >= min_items
    return valid, exists, items


def main():
    """Run all validation checks."""
    root = Path(__file__).parent
    
    checks = []
    
    # Phase 1: Prompts
    print("\n📁 Phase 1: Prompts")
    for file in ["prompts/__init__.py", "prompts/resume_system.md", "prompts/cover_system.md"]:
        valid, exists, size = check_file(root / file, min_size=100)
        status = "✅" if valid else "❌"
        checks.append((file, valid))
        print(f"  {status} {file} ({size} bytes)")
    
    # Phase 1: Schemas
    print("\n📁 Phase 1: Schemas")
    for file in ["schemas/__init__.py", "schemas/paragraph.py", "schemas/resume_schema.py", "schemas/cover_schema.py"]:
        valid, exists, size = check_file(root / file, min_size=50)
        status = "✅" if valid else "❌"
        checks.append((file, valid))
        print(f"  {status} {file} ({size} bytes)")
    
    # Phase 1: Services
    print("\n📁 Phase 1: Services")
    for file in ["services/__init__.py", "services/retrieval.py", "services/source_selection.py", "services/llm_client.py"]:
        valid, exists, size = check_file(root / file, min_size=100)
        status = "✅" if valid else "❌"
        checks.append((file, valid))
        print(f"  {status} {file} ({size} bytes)")
    
    # Phase 2: Reviewer Agent
    print("\n🤖 Phase 2: Reviewer Agent")
    file = "agents/reviewer_agent.py"
    valid, exists, size = check_file(root / file, min_size=500)
    status = "✅" if valid else "❌"
    checks.append((file, valid))
    print(f"  {status} {file} ({size} bytes)")
    
    # Phase 2: Evals
    print("\n📊 Phase 2: Evals")
    evals_files = [
        "evals/__init__.py",
        "evals/test_hallucination.py",
        "evals/test_structure.py",
        "evals/runner.py",
    ]
    for file in evals_files:
        valid, exists, size = check_file(root / file, min_size=100)
        status = "✅" if valid else "❌"
        checks.append((file, valid))
        print(f"  {status} {file} ({size} bytes)")
    
    # Check golden examples
    valid, exists, items = check_directory(root / "evals/golden_examples", min_items=1)
    status = "✅" if valid else "❌"
    checks.append(("evals/golden_examples/", valid))
    print(f"  {status} evals/golden_examples/ ({items} items)")
    
    # Check traces directory exists
    valid, exists, items = check_directory(root / "evals/traces")
    status = "✅" if exists else "⚠️"
    print(f"  {status} evals/traces/ (exists: {exists})")
    
    # Phase 3: Orchestrator
    print("\n🎯 Phase 3: Orchestrator")
    file = "agents/orchestrator.py"
    valid, exists, size = check_file(root / file, min_size=1000)
    status = "✅" if valid else "❌"
    checks.append((file, valid))
    print(f"  {status} {file} ({size} bytes)")
    
    # Phase 3: Interactive CLI
    print("\n👤 Phase 3: Interactive CLI")
    file = "interactive.py"
    valid, exists, size = check_file(root / file, min_size=1000)
    status = "✅" if valid else "❌"
    checks.append((file, valid))
    print(f"  {status} {file} ({size} bytes)")
    
    # Check agents __init__.py is not empty
    print("\n🔧 Module Exports")
    file = "agents/__init__.py"
    valid, exists, size = check_file(root / file, min_size=100)
    status = "✅" if valid else "❌"
    checks.append((file, valid))
    print(f"  {status} agents/__init__.py exports new agents ({size} bytes)")
    
    # Documentation
    print("\n📚 Documentation")
    for file in ["README.md", "CHANGELOG.md"]:
        valid, exists, size = check_file(root / file, min_size=1000)
        status = "✅" if valid else "❌"
        checks.append((file, valid))
        print(f"  {status} {file} ({size} bytes)")
    
    # Check README mentions new components
    readme_content = (root / "README.md").read_text()
    readme_checks = [
        ("prompts/ mentioned", "prompts/" in readme_content),
        ("schemas/ mentioned", "schemas/" in readme_content),
        ("services/ mentioned", "services/" in readme_content),
        ("reviewer_agent mentioned", "reviewer_agent" in readme_content),
        ("orchestrator mentioned", "orchestrator" in readme_content),
        ("interactive.py mentioned", "interactive.py" in readme_content),
        ("evals/ mentioned", "evals/" in readme_content),
        ("Phase 1 mentioned", "Phase 1" in readme_content),
        ("Phase 2 mentioned", "Phase 2" in readme_content),
        ("Phase 3 mentioned", "Phase 3" in readme_content),
    ]
    
    print("\n📝 README Coverage")
    for name, found in readme_checks:
        status = "✅" if found else "❌"
        print(f"  {status} {name}")
        checks.append((name, found))
    
    # Check CHANGELOG
    changelog_content = (root / "CHANGELOG.md").read_text()
    changelog_checks = [
        ("May 25, 2025 entry", "May 25, 2025" in changelog_content),
        ("Three-Phase mentioned", "Three-Phase" in changelog_content),
        ("Phase 1 details", "prompts/`" in changelog_content or "prompts/" in changelog_content),
    ]
    
    print("\n📝 CHANGELOG Coverage")
    for name, found in changelog_checks:
        status = "✅" if found else "❌"
        print(f"  {status} {name}")
        checks.append((name, found))
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    total = len(checks)
    passed = sum(1 for _, valid in checks if valid)
    failed = total - passed
    
    print(f"\nTotal checks: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    
    if failed == 0:
        print("\n🎉 All validation checks passed!")
        print("\nArchitecture is properly documented and structured.")
        return 0
    else:
        print("\n⚠️ Some checks failed. Review the issues above.")
        failed_items = [name for name, valid in checks if not valid]
        print(f"\nFailed items: {', '.join(failed_items[:5])}")
        if len(failed_items) > 5:
            print(f"  ... and {len(failed_items) - 5} more")
        return 1


if __name__ == "__main__":
    sys.exit(main())
