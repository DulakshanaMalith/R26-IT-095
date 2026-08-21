import os
import sys
import argparse
import json
from pathlib import Path

# Add src to python path for relative imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reviewer.service import run_review

def main():
    parser = argparse.ArgumentParser(description="Run autonomous LLM review on a proposal.")
    parser.add_argument("--input", required=True, type=str, help="Path to the proposal text file.")
    parser.add_argument("--mode", default="llm_only", choices=["llm_only", "llm_rag", "llm_rag_criteria"], help="The review mode.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File {input_path} not found.")
        sys.exit(1)

    proposal_text = input_path.read_text(encoding="utf-8")

    try:
        validated_result, metadata = run_review(
            proposal_text=proposal_text,
            mode=args.mode
        )
    except Exception as e:
        print(f"Generation failed: {e}")
        sys.exit(1)

    if args.json:
        output_dict = {
            "review": json.loads(validated_result.model_dump_json()),
            "metadata": metadata
        }
        print(json.dumps(output_dict, indent=2))
    else:
        print("="*60)
        print("PROPOSAL SUMMARY")
        print("="*60)
        print(validated_result.proposal_summary)
        print("\n" + "="*60)
        print("OVERALL ASSESSMENT")
        print("="*60)
        print(validated_result.overall_assessment)
        
        print("\n" + "="*60)
        print(f"WEAKNESSES ({len(validated_result.issues)})")
        print("="*60)
        for idx, issue in enumerate(validated_result.issues, 1):
            print(f"\n{idx}. [{issue.section}] - Severity: {issue.severity.upper()}")
            print(f"   Evidence: \"{issue.evidence_span}\"")
            print(f"   Reason: {issue.reason}")
            print(f"   Recommendation: {issue.recommendation}")
            
        print("\n" + "="*60)
        print(f"STRENGTHS ({len(validated_result.strengths)})")
        print("="*60)
        for idx, strength in enumerate(validated_result.strengths, 1):
            print(f"\n{idx}. [{strength.section}]")
            print(f"   Evidence: \"{strength.evidence_span}\"")
            print(f"   Reason: {strength.reason}")

if __name__ == "__main__":
    main()
