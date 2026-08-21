# Exposía

Exposía originated from the lecture “Introduction to Scientific Work” (Einführung in das wissenschaftliche Arbeiten) 
at the Technical University of Darmstadt, Germany.

Exposía contains the following data (if consent was given):

- Draft Exposé (PDF + LaTeX)
- Final Exposé (PDF + LaTeX)
- Reviews (HTML + Text + Edits) 
- Inline Comments (Highlights + Comments)
- Comment Votes
- Criteria Scores
- Templates

## Details

- Version: 1.0.0
- Author: Dennis Zyska <dennis.zyska@tu-darmstadt.de>
- Year: 2026
- Language: English
- License: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)
- Place: Technical University of Darmstadt, Germany
- Source: Lecture `Introduction in scientific work` (winter term 2024/2025) 

## Structure

Exposía is structured as follows:

```
- exposes                       - Exposé folder
    - "Expose Author"           - Each submission in a separate folder
        - draft/                - Draft submissions (PDF + LaTeX files)
        - final/                - Final submissions (PDF + LaTeX files)
        - annotations.json      - List of dictionaries with annotations
        - comments.json         - List of dictionaries with comments including votes
        - meta.json             - Meta information about the submission and reviews
        - scores.json           - List of dictionaries with scores (see `type` for the score target)
        - review_<i>.html       - HTML version of the i's review
        - review_<i>.txt        - Text version of the i's review
- reviews                       - Review submissions 
    - "Review Hash"             - Each submission in a separate folder
        - meta.json             - Meta information about the review
        - annotations.json      - List of dictionaries with annotations 
                                    (if `text` and `selectors` missing, consent was not given)
        - comments.json         - List of dictionaries with comments including votes
        - review.html           - HTML version of the i's review
        - review.txt            - Text version of the i's review
        - review.delta          - Delta format of the review (only if consent was given)
        - edits.csv             - Edits in original database format (only if consent was given)
- supplementary/                - Additional material
    - behaviour_data.csv        - Behavioral data of the participants (if consent was given)
    - dbToDelta.py              - Example Script to convert the database edits to delta format (Quill Editor)
    - expose_criteria.json      - Criterias for the exposé in json format
    - review_criteria.json      - Criterias for the review in json format    
- README.md                     - This file
```

### References

A list of key attributes shared across JSON files:

```
- author                            - Author of the exposé 
- reviewer                          - Author of the review
- hash                              - Unique hash of a review submission
- role                              - Role of the reviewer
                                        - student (students)
                                        - assistant (junior instructor)
                                        - expert (senior instructor)
- group                             - Group ID of the reviewer:
                                        1 - grading during the course
                                        2 - grading after the course
```


#### `meta.json`

```jsonc
{
    "topic": "String",      // The topic of the exposé
    "author": "String",
    "i": {
        "review": Integer,  // The i-th review
        "hash": "String", 
        "reviewer": "String",
        "role": "String",
        "size": Integer,    // Character count
        "group": Integer    
    }
}
```

#### `annotations.json`

```jsonc
[
    {
        "id": Integer,          // The unique ID of the annotation
        "user": "String",       // The reviewer author, would be equal to key "reviewer" in other files
        "role": "String",
        "text": "String",       // Annotated text from the Exposé
        "selectors": {          // Selectors used to identify the exact snippet in different ways (= "type")
            "target": [
                {
                    "selector": [
                        {
                            "end": Integer,
                            "type": "TextPositionSelector",     //using character indexing
                            "start": Integer
                        },
                        {
                            "type": "TextQuoteSelector",        //using text surrounding the snippet
                            "exact": "String",
                            "prefix": "String",
                            "suffix": "String"
                        },
                        {
                            "type": "PagePositionSelector",     //using the page number
                            "number": Integer
                        }
                    ]
                }
            ]
        },
        "tag": "String",        // category the annotation belongs to; ["Highlight", "Weakness", "Strength", "Other"]
        "review": Integer,      // the i-th review of the exposé
        "group": Integer         
    },
    {
        ...
    }
]
```


#### `comments.json`

```jsonc
[
    {
        "id": Integer,                      // The unique ID of the comment
        "user": "String",      
        "role": "String",
        "text": "String",                   // The content of the comment
        "annotationId": Integer,            // Foreign key referencing to 'id' in annotations.json. 
                                               Can be None for side comments.
        "parentCommentId": null or Integer, // If the comment is an answer to an existing comment, 
                                               ID of the original comment
        "tags":["String"],                  // List of tags (created by the reviewer) belongs to the comment, 
                                               Can be empty if no individual tags were added
        "review": i,                        // Review this comment belongs to, corresponding to files review_i
        "votes": [                          // List of votes, can be empty 
            {
                "user": "String", 
                "role": "String",
                "vote": Integer             //v1 = Upvote and -1 = Downvote
            }
        ], 
        "group": Integer
    },
    {
        ...
    }
]
```

#### `scores.json`

```jsonc
[
    {
        "author": "String",
        "group": Integer,
        "grader": "String",             // Name of the person doing the grading
        "role": "String",
        "hash": "String",               // Only exists if "type" == "review"
        "reviewer": "String",           // Only exists if "type" == "review"
        "type": "String",               // Is one of ["draft", "final", "review"]
        "scores": {                     // This part contains summarized points for rubrics and total points
            "form": {
                "structure": Integer,
                "language": Integer,
                "total": Integer
            },
            "content": {
                ...
            },
            "others": {
                ...
            },
            "total": Integer
        },
        "criteria": {                       // This part contains each criterion individually listed with their score
            "criterion_name": Integer,
            "criterion_name": Integer,
            ...
            "Additional infos": "String"    // Comment left by the grader
        }
    },
    {
        ...
    }
]
```

### Behavioral data

For participants who have explicitly consented to the collection of behavioral data, we provide detailed records.
Thereby it is separated into different types of actions (with additional information in the `data` field).

### Acknowledgments

This work has been funded by the German Research Foundation (DFG) as part of the PEER project (grant GU 798/28-1) 
and by the European Union (ERC, InterText, 101054961). Views and opinions expressed are, however, 
those of the author(s) only and do not necessarily reflect those of the European Union or the European Research Council.
Neither the European Union nor the granting authority can be held responsible for them.
The author would like to thank all student participants as well as the instructors involved in the course for their 
support in data collection and preparation.