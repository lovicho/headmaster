import os
import sys
from pathlib import Path

def main() -> None:
    # Find project root assuming this is in backend/scripts/sdd_validator.py
    # or run from project root
    current_dir = Path.cwd()
    if (current_dir / "plan").exists():
        project_root = current_dir
    else:
        project_root = Path(__file__).parent.parent.parent

    plan_dir = project_root / "plan"
    
    if not plan_dir.exists():
        print("❌ [SDD Validator] Error: 'plan' directory not found.")
        sys.exit(1)

    required_files = {
        "proposal.md": [
            "## 1.", "## 2."
        ],
        "design.md": [
            "## 1.", "## 2.", "## 3."
        ],
        "tasks.md": [
            "- ["
        ]
    }

    all_passed = True

    print("[SDD Validator] Checking Spec Driven Development 3-Tier files...")

    for filename, required_patterns in required_files.items():
        filepath = plan_dir / filename
        if not filepath.exists():
            print(f"[ERROR] Missing file: {filename}")
            all_passed = False
            continue
        
        content = filepath.read_text(encoding="utf-8")
        
        for pattern in required_patterns:
            if pattern not in content:
                print(f"[WARN] Missing required structure in {filename}: '{pattern}' not found.")
                all_passed = False

    if all_passed:
        print("[SUCCESS] All SDD specs are valid and synchronized.")
        sys.exit(0)
    else:
        print("[ERROR] SDD validation failed. Please fix the missing files or structures.")
        sys.exit(1)

if __name__ == "__main__":
    main()
