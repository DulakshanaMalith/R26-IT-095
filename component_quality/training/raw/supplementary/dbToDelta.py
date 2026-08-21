"""
This script generates a delta file for the Quill Editor from a csv file in that dataset.

Requirements:

quill-delta>=1.0.3
pandas>=2.0.3
"""
__author__ = "Dennis Zyska, Juliane Bechert"
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Dennis Zyska"
__email__ = "dennis.zyska@tu-darmstadt.de"

import argparse
from delta import Delta
from datetime import datetime
import json
import pandas as pd


def get_parser():
    parser = argparse.ArgumentParser(
        description='Generate a delta file for the Quill Editor from a csv file in that dataset.')
    parser.add_argument('--csv', type=str, help='Path to the csv file')
    parser.add_argument('--delta', type=str, help='Path to the output delta file')

    # set default values
    parser.set_defaults(
        csv='./edits.csv',
        delta='./edits.delta',
    )

    return parser


def db_to_delta(db_entries):
    """
    Convert a list of database entries to a Quill Delta object.
    :param db_entries: List of database entries, each entry is a dict
    :return: quill delta object
    """

    # Sort entries by createdAt, then by `order` (default 0)
    sorted_entries = sorted(
        db_entries,
        key=lambda e: (
            datetime.fromisoformat(e['createdAt'].replace("Z", "+00:00")),
            e.get('order', 0)
        )
    )

    composite_delta = Delta()

    for edit in sorted_entries:
        operation_type = edit['operationType']
        offset = edit['offset']
        span = edit['span']
        text = edit.get('text')

        # Safely parse 'attributes' whether it's a dict or string
        attributes = edit.get('attributes') or {}

        delta = Delta()

        if operation_type == 0:  # Insert
            delta.push({"retain": offset})
            insert_op = {"insert": text}
            if attributes:
                insert_op["attributes"] = attributes
            delta.push(insert_op)

        elif operation_type == 1:  # Delete
            delta.push({"retain": offset})
            delta.push({"delete": span})

        elif operation_type == 2:  # Retain with attributes
            delta.push({"retain": offset})
            retain_op = {"retain": span}
            if attributes:
                retain_op["attributes"] = attributes
            delta.push(retain_op)

        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        composite_delta = composite_delta.compose(delta)

    return composite_delta


if __name__ == "__main__":
    arg_parser = get_parser()
    args = arg_parser.parse_args()

    with open(args.csv, "r", encoding="utf-8") as source:
        df = pd.read_csv(source)

        # Parse 'attributes' back to dict
        df['attributes'] = df['attributes'].apply(
            lambda x: json.loads(x) if isinstance(x, str) and x.startswith('{') else {}
        )

        edits = df.to_dict(orient='records')
        deltas = db_to_delta(edits)
        with open(args.delta, "w") as target:
            target.write(json.dumps(deltas.ops, indent=4, ensure_ascii=False, allow_nan=False))
