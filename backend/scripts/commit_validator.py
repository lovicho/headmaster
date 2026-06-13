import sys
import re

def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(0)
    
    commit_msg_file = sys.argv[1]
    with open(commit_msg_file, "r", encoding="utf-8") as f:
        msg = f.read()

    # Ignore automatically generated merge commits
    if msg.startswith("Merge branch") or msg.startswith("Merge pull request"):
        sys.exit(0)

    # Check for [task: ...] tag
    if not re.search(r"\[task:[^\]]+\]", msg):
        print("[ERROR] Commit Validator Failed!")
        print("Commit message must include a task tracking tag to ensure traceability with plan/tasks.md.")
        print("Example: 'Fix orchestrator resume bug [task: 에러 복구 경계 강화]'")
        print("Or if no task applies: 'Update documentation [task: none]'")
        sys.exit(1)
        
    print("[SUCCESS] Commit message task traceability validated.")
    sys.exit(0)

if __name__ == "__main__":
    main()
