from typing import Dict, Iterable, List, Tuple

ObjectivePoint = Tuple[float, float]

DEFAULT_REFERENCE_POINT: ObjectivePoint = (
    1.01,
    1.01,
)

def dominates(
    point_a: ObjectivePoint,
    point_b: ObjectivePoint,
) -> bool:
    """
    Pareto dominance for two minimization objectives.

    A dominates B when A is no worse in either
    objective and strictly better in at least one.
    """

    a_f1, a_f2 = point_a
    b_f1, b_f2 = point_b

    return (
        a_f1 <= b_f1
        and a_f2 <= b_f2
        and (
            a_f1 < b_f1
            or a_f2 < b_f2
        )
    )

def normalize_point(
    point: ObjectivePoint,
) -> ObjectivePoint:
    return (
        round(float(point[0]), 12),
        round(float(point[1]), 12),
    )

def extract_objective_points(
    pareto_front: Iterable[Dict],
) -> List[ObjectivePoint]:
    points = []

    for item in pareto_front:
        if (
            "technical_requirement_deficit"
            not in item
        ):
            raise ValueError(
                "Pareto-front item is missing "
                "'technical_requirement_deficit'."
            )

        if (
            "preference_dissatisfaction"
            not in item
        ):
            raise ValueError(
                "Pareto-front item is missing "
                "'preference_dissatisfaction'."
            )

        point = normalize_point(
            (
                item[
                    "technical_requirement_deficit"
                ],
                item[
                    "preference_dissatisfaction"
                ],
            )
        )

        points.append(
            point
        )

    return points

def get_nondominated_points(
    points: Iterable[ObjectivePoint],
) -> List[ObjectivePoint]:
    """
    Remove duplicate and dominated objective points.
    """

    unique_points = sorted(
        {
            normalize_point(
                point
            )
            for point in points
        }
    )

    nondominated = []

    for candidate in unique_points:
        is_dominated = any(
            dominates(
                other,
                candidate,
            )
            for other in unique_points
            if other != candidate
        )

        if not is_dominated:
            nondominated.append(
                candidate
            )

    nondominated.sort(
        key=lambda point: (
            point[0],
            point[1],
        )
    )

    return nondominated

def validate_reference_point(
    reference_point: ObjectivePoint,
) -> None:
    ref_f1, ref_f2 = reference_point

    if ref_f1 <= 0:
        raise ValueError(
            "Hypervolume reference f1 "
            "must be greater than 0."
        )

    if ref_f2 <= 0:
        raise ValueError(
            "Hypervolume reference f2 "
            "must be greater than 0."
        )

def calculate_hypervolume_2d(
    points: Iterable[ObjectivePoint],
    reference_point: ObjectivePoint = (
        DEFAULT_REFERENCE_POINT
    ),
) -> float:
    """
    Calculate exact 2D hypervolume for minimization.

    Both objectives are minimized.

    The default reference point (1.01, 1.01)
    is slightly worse than the valid normalized
    objective range [0, 1].

    Higher hypervolume indicates a better
    nondominated front.
    """

    validate_reference_point(
        reference_point
    )

    ref_f1, ref_f2 = (
        reference_point
    )

    nondominated = (
        get_nondominated_points(
            points
        )
    )

    valid_points = []

    for f1, f2 in nondominated:
        if f1 < 0 or f2 < 0:
            raise ValueError(
                "Objective values cannot "
                "be negative."
            )

        if (
            f1 >= ref_f1
            or f2 >= ref_f2
        ):
            continue

        valid_points.append(
            (f1, f2)
        )

    if not valid_points:
        return 0.0

    valid_points.sort(
        key=lambda point: (
            point[0],
            -point[1],
        )
    )

    hypervolume = 0.0
    previous_f2 = ref_f2

    for f1, f2 in valid_points:
        if f2 >= previous_f2:
            continue

        width = (
            ref_f1
            - f1
        )

        height = (
            previous_f2
            - f2
        )

        hypervolume += (
            width
            * height
        )

        previous_f2 = f2

    return hypervolume

def calculate_front_metrics(
    pareto_front: Iterable[Dict],
    reference_point: ObjectivePoint = (
        DEFAULT_REFERENCE_POINT
    ),
) -> Dict:
    """
    Calculate summary metrics for a discovered
    multi-objective front.
    """

    raw_points = (
        extract_objective_points(
            pareto_front
        )
    )

    nondominated_points = (
        get_nondominated_points(
            raw_points
        )
    )

    if not nondominated_points:
        return {
            "raw_point_count": 0,
            "nondominated_point_count": 0,
            "best_technical_deficit": None,
            "best_preference_dissatisfaction": None,
            "hypervolume": 0.0,
            "reference_point": {
                "technical_requirement_deficit": (
                    reference_point[0]
                ),
                "preference_dissatisfaction": (
                    reference_point[1]
                ),
            },
            "nondominated_points": [],
        }

    best_technical_deficit = min(
        point[0]
        for point
        in nondominated_points
    )

    best_preference_dissatisfaction = min(
        point[1]
        for point
        in nondominated_points
    )

    hypervolume = (
        calculate_hypervolume_2d(
            points=nondominated_points,
            reference_point=(
                reference_point
            ),
        )
    )

    return {
        "raw_point_count": len(
            raw_points
        ),
        "nondominated_point_count": len(
            nondominated_points
        ),
        "best_technical_deficit": (
            best_technical_deficit
        ),
        "best_preference_dissatisfaction": (
            best_preference_dissatisfaction
        ),
        "hypervolume": (
            hypervolume
        ),
        "reference_point": {
            "technical_requirement_deficit": (
                reference_point[0]
            ),
            "preference_dissatisfaction": (
                reference_point[1]
            ),
        },
        "nondominated_points": [
            {
                "technical_requirement_deficit": (
                    point[0]
                ),
                "preference_dissatisfaction": (
                    point[1]
                ),
            }
            for point in nondominated_points
        ],
    }