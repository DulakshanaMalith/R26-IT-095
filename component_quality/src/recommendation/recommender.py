def recommend_resources(weaknesses):
    resource_db = {
        "Literature Review": [
            {
                "type": "guide",
                "title": "How to write a critical literature review"
            },
            {
                "type": "youtube",
                "title": "How to Write a Literature Review (Step-by-Step)",
                "url": "https://www.youtube.com/watch?v=2IUZWZX4OGI"
            },
            {
                "type": "link",
                "title": "Best practices for literature synthesis",
                "url": "https://libguides.usc.edu/writingguide/literaturereview"
            }
        ],

        "Research Gap": [
            {
                "type": "youtube",
                "title": "How to Identify a Research Gap",
                "url": "https://www.youtube.com/watch?v=8F7u8X8zF9A"
            },
            {
                "type": "link",
                "title": "Finding Research Gaps Guide",
                "url": "https://research-methodology.net/research-methodology/research-gap/"
            }
        ],

        "Methodology": [
            {
                "type": "youtube",
                "title": "How to Write Research Methodology",
                "url": "https://www.youtube.com/watch?v=YbQyB2dC6dM"
            },
            {
                "type": "link",
                "title": "Methodology Writing Guide",
                "url": "https://www.scribbr.com/dissertation/methodology/"
            }
        ],

        "SMART Objectives": [
            {
                "type": "youtube",
                "title": "SMART Goals Explained Clearly",
                "url": "https://www.youtube.com/watch?v=1-SvuFIQjK8"
            },
            {
                "type": "link",
                "title": "How to Write SMART Objectives",
                "url": "https://www.mindtools.com/pages/article/smart-goals.htm"
            }
        ],

        "Academic Writing and References": [
            {
                "type": "youtube",
                "title": "Academic Writing for Beginners",
                "url": "https://www.youtube.com/watch?v=Q4dV6yCwZ7s"
            },
            {
                "type": "link",
                "title": "Referencing and Citation Guide",
                "url": "https://www.citethisforme.com/"
            }
        ]
    }

    recommendations = {}

    for w in weaknesses:
        criterion = w["criterion"]
        if criterion in resource_db:
            recommendations[criterion] = resource_db[criterion]

    return recommendations