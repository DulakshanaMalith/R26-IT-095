"""Tests for data joining and datasets construction."""

import pandas as pd
from exposia.datasets import build_master_dataset

def test_master_join():
    anns = pd.DataFrame([
        {"annotation_id": "a1", "author": "Alice", "annotation_tag": "Weakness"},
        {"annotation_id": "a2", "author": "Bob", "annotation_tag": "Strength"}
    ])
    
    comments = pd.DataFrame([
        {"comment_id": "c1", "annotation_id": "a1", "comment_text": "Good point", "author_comment": "Alice"},
        {"comment_id": "c2", "annotation_id": None, "comment_text": "Side comment", "author_comment": "Charlie"}
    ])
    
    exposes = pd.DataFrame([
        {"author": "Alice", "topic": "CS", "draft_text": "Text A", "final_text": "Final A"},
        {"author": "Bob", "topic": "Math", "draft_text": "Text B", "final_text": "Final B"}
    ])
    
    master = build_master_dataset(exposes, pd.DataFrame(), anns, comments)
    
    # 3 rows total: 2 annotations (one with comment, one without) + 1 side comment
    assert len(master) == 3
    
    # Check side comment
    side = master[master["comment_id"] == "c2"].iloc[0]
    assert side["comment_text"] == "Side comment"
    assert pd.isna(side["annotation_id"])
    
    # Check orphaned annotation
    orph = master[master["annotation_id"] == "a2"].iloc[0]
    assert orph["annotation_tag"] == "Strength"
    assert pd.isna(orph["comment_id"])
