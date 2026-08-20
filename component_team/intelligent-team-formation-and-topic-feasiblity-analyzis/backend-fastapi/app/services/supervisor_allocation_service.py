from collections import deque
from typing import Dict, List, Set, Tuple

from app.models.cohort_import import CohortImportData


def _normalize_domain(value: str) -> str:
    return str(value).strip().casefold()


def _build_project_domain_maps(
    data: CohortImportData,
) -> Tuple[
    Dict[str, Set[str]],
    Dict[str, Dict[str, str]],
]:
    normalized = {}
    display = {}

    for item in data.project_domains:
        project_id = item.project_id
        domain = item.domain.strip()
        key = _normalize_domain(domain)

        normalized.setdefault(
            project_id,
            set(),
        ).add(key)

        display.setdefault(
            project_id,
            {},
        )[key] = domain

    return normalized, display


def _build_supervisor_domain_maps(
    data: CohortImportData,
):
    expertise = {}
    interests = {}
    display = {}

    for item in data.supervisor_domains:
        supervisor_id = (
            item.supervisor_id
        )

        domain = item.domain.strip()
        key = _normalize_domain(
            domain
        )

        display.setdefault(
            supervisor_id,
            {},
        )[key] = domain

        if item.type == "Expertise":
            expertise.setdefault(
                supervisor_id,
                set(),
            ).add(key)

        elif item.type == "Interest":
            interests.setdefault(
                supervisor_id,
                set(),
            ).add(key)

    return (
        expertise,
        interests,
        display,
    )


def _match_status(
    project_domains: Set[str],
    expertise_matches: Set[str],
    interest_matches: Set[str],
) -> str:
    if (
        project_domains
        and expertise_matches
        == project_domains
    ):
        return (
            "Strong Expertise Match"
        )

    if expertise_matches:
        return "Expertise Match"

    if interest_matches:
        return "Interest Match"

    return "Capacity-Only Assignment"


class _Edge:
    def __init__(
        self,
        to: int,
        reverse: int,
        capacity: int,
        cost: int,
    ):
        self.to = to
        self.reverse = reverse
        self.capacity = capacity
        self.cost = cost


def _add_edge(
    graph: List[List[_Edge]],
    source: int,
    target: int,
    capacity: int,
    cost: int,
):
    forward = _Edge(
        to=target,
        reverse=len(
            graph[target]
        ),
        capacity=capacity,
        cost=cost,
    )

    backward = _Edge(
        to=source,
        reverse=len(
            graph[source]
        ),
        capacity=0,
        cost=-cost,
    )

    graph[source].append(
        forward
    )

    graph[target].append(
        backward
    )

    return len(
        graph[source]
    ) - 1


def _min_cost_flow(
    graph: List[List[_Edge]],
    source: int,
    sink: int,
    required_flow: int,
) -> Tuple[int, int]:
    flow = 0
    total_cost = 0
    node_count = len(graph)

    while flow < required_flow:
        infinity = 10**30

        distance = [
            infinity
        ] * node_count

        previous_node = [
            -1
        ] * node_count

        previous_edge = [
            -1
        ] * node_count

        in_queue = [
            False
        ] * node_count

        queue = deque(
            [source]
        )

        distance[source] = 0
        in_queue[source] = True

        while queue:
            node = queue.popleft()
            in_queue[node] = False

            for edge_index, edge in enumerate(
                graph[node]
            ):
                if edge.capacity <= 0:
                    continue

                new_distance = (
                    distance[node]
                    + edge.cost
                )

                if (
                    new_distance
                    < distance[edge.to]
                ):
                    distance[
                        edge.to
                    ] = new_distance

                    previous_node[
                        edge.to
                    ] = node

                    previous_edge[
                        edge.to
                    ] = edge_index

                    if not in_queue[
                        edge.to
                    ]:
                        queue.append(
                            edge.to
                        )

                        in_queue[
                            edge.to
                        ] = True

        if distance[sink] == infinity:
            break

        added_flow = (
            required_flow
            - flow
        )

        node = sink

        while node != source:
            parent = (
                previous_node[node]
            )

            edge_index = (
                previous_edge[node]
            )

            if parent == -1:
                added_flow = 0
                break

            edge = graph[
                parent
            ][edge_index]

            added_flow = min(
                added_flow,
                edge.capacity,
            )

            node = parent

        if added_flow <= 0:
            break

        node = sink

        while node != source:
            parent = (
                previous_node[node]
            )

            edge_index = (
                previous_edge[node]
            )

            edge = graph[
                parent
            ][edge_index]

            edge.capacity -= (
                added_flow
            )

            reverse_edge = graph[
                node
            ][edge.reverse]

            reverse_edge.capacity += (
                added_flow
            )

            node = parent

        flow += added_flow

        total_cost += (
            added_flow
            * distance[sink]
        )

    return flow, total_cost


def allocate_supervisors(
    data: CohortImportData,
) -> Dict:
    projects = sorted(
        data.projects,
        key=lambda item: (
            item.project_id
        ),
    )

    supervisors = sorted(
        data.supervisors,
        key=lambda item: (
            item.supervisor_id
        ),
    )

    if not projects:
        raise ValueError(
            "No projects are available "
            "for supervisor allocation."
        )

    if not supervisors:
        raise ValueError(
            "No supervisors are available "
            "for supervisor allocation."
        )

    (
        project_domains,
        project_domain_display,
    ) = _build_project_domain_maps(
        data
    )

    (
        supervisor_expertise,
        supervisor_interests,
        supervisor_domain_display,
    ) = _build_supervisor_domain_maps(
        data
    )

    available_slots = []

    for supervisor in supervisors:
        remaining_capacity = max(
            0,
            supervisor.maximum_teams
            - supervisor.current_load,
        )

        for slot_number in range(
            1,
            remaining_capacity + 1,
        ):
            projected_load = (
                supervisor.current_load
                + slot_number
            )

            utilization = (
                projected_load
                / supervisor.maximum_teams
            )

            available_slots.append(
                {
                    "supervisor": (
                        supervisor
                    ),
                    "slot_number": (
                        slot_number
                    ),
                    "projected_load": (
                        projected_load
                    ),
                    "utilization": (
                        utilization
                    ),
                }
            )

    if len(
        available_slots
    ) < len(projects):
        raise ValueError(
            "Supervisor capacity is "
            "insufficient for the number "
            "of project teams."
        )

    slot_order = sorted(
        range(
            len(available_slots)
        ),
        key=lambda index: (
            available_slots[
                index
            ]["utilization"],
            available_slots[
                index
            ]["supervisor"]
            .current_load,
            available_slots[
                index
            ]["supervisor"]
            .supervisor_id,
            available_slots[
                index
            ]["slot_number"],
        ),
    )

    load_bonus = {}

    total_slots = len(
        available_slots
    )

    for rank, slot_index in enumerate(
        slot_order
    ):
        load_bonus[
            slot_index
        ] = (
            total_slots - rank
        )

    max_project_domains = max(
        (
            len(
                project_domains.get(
                    project.project_id,
                    set(),
                )
            )
            for project in projects
        ),
        default=1,
    )

    base = (
        len(projects)
        * max(
            max_project_domains,
            total_slots,
            1,
        )
        + 1
    )

    project_count = len(
        projects
    )

    source = 0
    project_offset = 1
    slot_offset = (
        project_offset
        + project_count
    )

    sink = (
        slot_offset
        + total_slots
    )

    graph = [
        []
        for _ in range(
            sink + 1
        )
    ]

    for project_index in range(
        project_count
    ):
        _add_edge(
            graph,
            source,
            project_offset
            + project_index,
            1,
            0,
        )

    for slot_index in range(
        total_slots
    ):
        _add_edge(
            graph,
            slot_offset
            + slot_index,
            sink,
            1,
            0,
        )

    assignment_edges = {}

    pair_details = {}

    for project_index, project in enumerate(
        projects
    ):
        project_id = (
            project.project_id
        )

        required_domains = (
            project_domains.get(
                project_id,
                set(),
            )
        )

        for slot_index, slot in enumerate(
            available_slots
        ):
            supervisor = (
                slot["supervisor"]
            )

            supervisor_id = (
                supervisor.supervisor_id
            )

            expertise_domains = (
                supervisor_expertise.get(
                    supervisor_id,
                    set(),
                )
            )

            interest_domains = (
                supervisor_interests.get(
                    supervisor_id,
                    set(),
                )
            )

            expertise_matches = (
                required_domains
                & expertise_domains
            )

            interest_matches = (
                required_domains
                & interest_domains
            )

            expertise_flag = int(
                bool(
                    expertise_matches
                )
            )

            interest_flag = int(
                bool(
                    interest_matches
                )
            )

            expertise_count = len(
                expertise_matches
            )

            interest_count = len(
                interest_matches
            )

            utility = (
                expertise_flag
                * (base**4)
                + expertise_count
                * (base**3)
                + interest_flag
                * (base**2)
                + interest_count
                * base
                + load_bonus[
                    slot_index
                ]
            )

            project_node = (
                project_offset
                + project_index
            )

            slot_node = (
                slot_offset
                + slot_index
            )

            edge_index = _add_edge(
                graph,
                project_node,
                slot_node,
                1,
                -utility,
            )

            assignment_edges[
                (
                    project_index,
                    slot_index,
                )
            ] = edge_index

            pair_details[
                (
                    project_index,
                    slot_index,
                )
            ] = {
                "required_domains": (
                    required_domains
                ),
                "expertise_matches": (
                    expertise_matches
                ),
                "interest_matches": (
                    interest_matches
                ),
            }

    flow, _ = _min_cost_flow(
        graph=graph,
        source=source,
        sink=sink,
        required_flow=(
            project_count
        ),
    )

    if flow != project_count:
        raise ValueError(
            "A complete supervisor "
            "allocation could not be "
            "generated."
        )

    selected_assignments = []

    supervisor_new_counts = {}

    for project_index, project in enumerate(
        projects
    ):
        selected_slot_index = None

        project_node = (
            project_offset
            + project_index
        )

        for slot_index in range(
            total_slots
        ):
            edge_index = (
                assignment_edges[
                    (
                        project_index,
                        slot_index,
                    )
                ]
            )

            edge = graph[
                project_node
            ][edge_index]

            if edge.capacity == 0:
                selected_slot_index = (
                    slot_index
                )
                break

        if selected_slot_index is None:
            raise ValueError(
                f"No supervisor was "
                f"assigned to project "
                f"'{project.project_id}'."
            )

        slot = available_slots[
            selected_slot_index
        ]

        supervisor = slot[
            "supervisor"
        ]

        supervisor_id = (
            supervisor.supervisor_id
        )

        supervisor_new_counts[
            supervisor_id
        ] = (
            supervisor_new_counts.get(
                supervisor_id,
                0,
            )
            + 1
        )

        detail = pair_details[
            (
                project_index,
                selected_slot_index,
            )
        ]

        selected_assignments.append(
            {
                "project": (
                    project
                ),
                "supervisor": (
                    supervisor
                ),
                "detail": (
                    detail
                ),
            }
        )

    results = []

    expertise_project_count = 0
    interest_project_count = 0
    no_domain_match_count = 0

    for assignment in (
        selected_assignments
    ):
        project = assignment[
            "project"
        ]

        supervisor = assignment[
            "supervisor"
        ]

        detail = assignment[
            "detail"
        ]

        required_domains = detail[
            "required_domains"
        ]

        expertise_matches = detail[
            "expertise_matches"
        ]

        interest_matches = detail[
            "interest_matches"
        ]

        if expertise_matches:
            expertise_project_count += 1

        if interest_matches:
            interest_project_count += 1

        if (
            not expertise_matches
            and not interest_matches
        ):
            no_domain_match_count += 1

        assigned_count = (
            supervisor_new_counts[
                supervisor.supervisor_id
            ]
        )

        projected_load = (
            supervisor.current_load
            + assigned_count
        )

        remaining_after = (
            supervisor.maximum_teams
            - projected_load
        )

        status = _match_status(
            project_domains=(
                required_domains
            ),
            expertise_matches=(
                expertise_matches
            ),
            interest_matches=(
                interest_matches
            ),
        )

        project_display = (
            project_domain_display.get(
                project.project_id,
                {},
            )
        )

        supervisor_display = (
            supervisor_domain_display.get(
                supervisor.supervisor_id,
                {},
            )
        )

        displayed_project_domains = sorted(
            project_display.get(
                domain,
                domain,
            )
            for domain in required_domains
        )

        displayed_expertise_matches = sorted(
            project_display.get(
                domain,
                supervisor_display.get(
                    domain,
                    domain,
                ),
            )
            for domain in expertise_matches
        )

        displayed_interest_matches = sorted(
            project_display.get(
                domain,
                supervisor_display.get(
                    domain,
                    domain,
                ),
            )
            for domain in interest_matches
        )

        explanation_parts = []

        if displayed_expertise_matches:
            explanation_parts.append(
                "Expertise match: "
                + ", ".join(
                    displayed_expertise_matches
                )
                + "."
            )

        if displayed_interest_matches:
            explanation_parts.append(
                "Interest match: "
                + ", ".join(
                    displayed_interest_matches
                )
                + "."
            )

        if (
            not displayed_expertise_matches
            and not displayed_interest_matches
        ):
            explanation_parts.append(
                "No direct project-domain "
                "match was available; the "
                "assignment was made using "
                "remaining supervisor capacity "
                "and workload as the final "
                "priority."
            )

        explanation_parts.append(
            "Capacity constraint satisfied."
        )

        results.append(
            {
                "project_id": (
                    project.project_id
                ),
                "project_title": (
                    project.project_title
                ),
                "project_domains": (
                    displayed_project_domains
                ),
                "supervisor_id": (
                    supervisor.supervisor_id
                ),
                "supervisor_name": (
                    supervisor.supervisor_name
                ),
                "match_status": (
                    status
                ),
                "expertise_matches": (
                    displayed_expertise_matches
                ),
                "interest_matches": (
                    displayed_interest_matches
                ),
                "current_load": (
                    supervisor.current_load
                ),
                "maximum_teams": (
                    supervisor.maximum_teams
                ),
                "new_teams_assigned": (
                    assigned_count
                ),
                "projected_load": (
                    projected_load
                ),
                "remaining_capacity": (
                    remaining_after
                ),
                "explanation": (
                    " ".join(
                        explanation_parts
                    )
                ),
            }
        )

    used_supervisors = len(
        {
            result[
                "supervisor_id"
            ]
            for result in results
        }
    )

    return {
        "algorithm": (
            "Global Lexicographic "
            "Supervisor Allocation"
        ),
        "research_scope": (
            "Downstream system/demo feature. "
            "This allocation method is not a "
            "third NSGA-II objective and was "
            "not part of the team-formation "
            "experimental evaluation."
        ),
        "priority_order": [
            (
                "Supervisor capacity "
                "(hard constraint)"
            ),
            (
                "Project-domain expertise "
                "match"
            ),
            (
                "Number of expertise domains "
                "matched"
            ),
            (
                "Project-domain research "
                "interest match"
            ),
            (
                "Number of interest domains "
                "matched"
            ),
            (
                "Lower projected workload"
            ),
        ],
        "summary": {
            "projects_assigned": (
                len(results)
            ),
            "supervisors_used": (
                used_supervisors
            ),
            "projects_with_expertise_match": (
                expertise_project_count
            ),
            "projects_with_interest_match": (
                interest_project_count
            ),
            "projects_without_domain_match": (
                no_domain_match_count
            ),
        },
        "assignments": results,
        "interpretation": (
            "The allocation is generated "
            "globally so supervisor capacity "
            "is respected across all projects. "
            "Expertise is prioritized over "
            "research interest, while workload "
            "is used only as a lower-priority "
            "tie-break criterion."
        ),
    }