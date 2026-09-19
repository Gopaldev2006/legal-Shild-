import os
import json
from typing import List, Dict, Any


PUBLIC_ACADEMIC_LEGAL_INSTRUCTIONS: List[Dict[str, Any]] = [
    {
        "id": "inst_1",
        "instruction": "Analyze the legal precedent set by Kesavananda Bharati v. State of Kerala.",
        "context": "Kesavananda Bharati v. State of Kerala (1973): 13-Judge Constitution Bench established the Basic Structure Doctrine restricting Parliament's amending power under Article 368.",
        "response": "The Kesavananda Bharati decision established that Parliament possesses wide constitutional amending power under Article 368, but cannot alter or destroy the Basic Structure of the Indian Constitution (including secularism, judicial review, and federalism)."
    },
    {
        "id": "inst_2",
        "instruction": "Explain the applicability of Part I of the Arbitration Act 1996 to foreign-seated arbitrations under BALCO (2012).",
        "context": "Bharat Aluminium Co. v. Kaiser Aluminium (2012): Supreme Court Constitution Bench overruled Bhatia International prospectively regarding foreign-seated arbitrations.",
        "response": "Under BALCO (2012), Part I of the Arbitration and Conciliation Act 1996 does not apply to foreign-seated arbitrations. Indian courts cannot grant interim relief under Section 9 for foreign-seated arbitrations unless explicitly agreed under post-2015 amendments."
    },
    {
        "id": "inst_3",
        "instruction": "What is the standard of liability established in M.C. Mehta v. Union of India for hazardous industries?",
        "context": "M.C. Mehta (Oleum Gas Leak Case, 1986): Supreme Court formulated the doctrine of Absolute Liability for hazardous industrial units operating in populated regions.",
        "response": "M.C. Mehta established the doctrine of Absolute Liability. Hazardous and inherently dangerous industrial enterprises owe an absolute, non-delegable duty to the community, and liability is absolute without Rylands v. Fletcher exceptions."
    },
    {
        "id": "inst_4",
        "instruction": "How does stamp duty deficiency impact Section 11 arbitrator appointments under N.N. Global (2023)?",
        "context": "N.N. Global Mercantile v. Indo Unique Flame (2023): Constitution Bench held 3:2 that an unstamped contract cannot be acted upon until impounded.",
        "response": "N.N. Global (2023) held that an unstamped or insufficiently stamped commercial contract containing an arbitration clause is unenforceable until impounded and stamped under the relevant Stamp Act, preventing Section 11 appointment until rectified."
    },
    {
        "id": "inst_5",
        "instruction": "What is the judicial review standard for executive economic policy decisions under BALCO Disinvestment (2001)?",
        "context": "BALCO Employees Union v. Union of India (2001): Trade union challenged BALCO disinvestment under Articles 14 and 21.",
        "response": "BALCO Disinvestment (2001) established that executive economic policy decisions are not subject to judicial review under Article 32 unless demonstrated to be arbitrary, unconstitutional, or mala fide."
    }
]


def prepare_and_split_dataset(output_dir: str = None) -> Dict[str, str]:
    """
    Formats public academic legal instruction data, splits into train and validation sets,
    and saves JSON datasets under output_dir.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "datasets")

    os.makedirs(output_dir, exist_ok=True)

    # 80/20 train/val split
    split_idx = int(len(PUBLIC_ACADEMIC_LEGAL_INSTRUCTIONS) * 0.8)
    train_data = PUBLIC_ACADEMIC_LEGAL_INSTRUCTIONS[:split_idx]
    val_data = PUBLIC_ACADEMIC_LEGAL_INSTRUCTIONS[split_idx:]

    train_file = os.path.join(output_dir, "train.json")
    val_file = os.path.join(output_dir, "val.json")

    with open(train_file, "w", encoding="utf-8") as f:
        json.dump(train_data, f, indent=2)

    with open(val_file, "w", encoding="utf-8") as f:
        json.dump(val_data, f, indent=2)

    print(f"Dataset preparation complete: {len(train_data)} train samples, {len(val_data)} validation samples.")
    return {"train": train_file, "val": val_file}


if __name__ == "__main__":
    prepare_and_split_dataset()
