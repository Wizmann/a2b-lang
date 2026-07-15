"""Diversity, isomorphism, balance, and representative-task statistics."""

from collections import Counter, defaultdict

from .diversity import diversity_distributions


def structural_cluster_report(problems):
    clusters = defaultdict(list)
    semantic_clusters = defaultdict(list)
    for problem in problems:
        clusters[problem.structural_fingerprint].append(problem.id)
        semantic_clusters[problem.semantic_fingerprint].append(problem.id)
    clustered = {
        fingerprint: sorted(ids)
        for fingerprint, ids in clusters.items()
        if len(ids) > 1
    }
    alpha_members = sum(len(ids) for ids in clustered.values())
    return {
        "cluster_count": len(clusters),
        "cluster_size_distribution": dict(
            Counter(len(ids) for ids in clusters.values())
        ),
        "largest_clusters": sorted(
            (
                {"fingerprint": fingerprint, "size": len(ids), "problem_ids": sorted(ids)}
                for fingerprint, ids in clustered.items()
            ),
            key=lambda item: (-item["size"], item["fingerprint"]),
        )[:30],
        "alpha_equivalent_fraction": alpha_members / len(problems) if problems else 0.0,
        "semantic_cluster_count": len(semantic_clusters),
    }


def _uniqueness_scores(problems):
    concept_counts = Counter(
        concept
        for problem in problems
        for concept in problem.generated_program.concepts
    )
    family_counts = Counter(
        problem.generated_program.algorithm_family for problem in problems
    )
    structure_counts = Counter(problem.structural_fingerprint for problem in problems)
    semantic_counts = Counter(problem.semantic_fingerprint for problem in problems)
    scores = []
    for problem in problems:
        generated = problem.generated_program
        concept_score = sum(1 / concept_counts[c] for c in generated.concepts) / len(
            generated.concepts
        )
        score = (
            concept_score
            + 1 / family_counts[generated.algorithm_family]
            + 1 / structure_counts[problem.structural_fingerprint]
            + 1 / semantic_counts[problem.semantic_fingerprint]
        )
        scores.append((score, problem))
    return sorted(scores, key=lambda item: (-item[0], item[1].id))


def representative_tasks(problems, count=15):
    selected = []
    seen = set()
    ordered = sorted(
        problems,
        key=lambda problem: (
            problem.generated_program.task_domain,
            problem.generated_program.source_type,
            problem.generated_program.composition_depth,
            problem.id,
        ),
    )
    for problem in ordered:
        generated = problem.generated_program
        key = (
            generated.task_domain,
            generated.source_type,
            generated.composition_depth,
        )
        if key not in seen:
            seen.add(key)
            selected.append(problem)
        if len(selected) >= count:
            break
    if len(selected) < count:
        for problem in ordered:
            if problem not in selected:
                selected.append(problem)
            if len(selected) >= count:
                break
    return tuple(selected)


def problem_summary(problem, uniqueness=None):
    generated = problem.generated_program
    result = {
        "id": problem.id,
        "task_domain": generated.task_domain,
        "algorithm_family": generated.algorithm_family,
        "source_type": generated.source_type,
        "composition_depth": generated.composition_depth,
        "concepts": list(generated.concepts),
        "description_style": generated.description_style,
        "description": generated.description,
        "program_lines": len(generated.program.splitlines()),
        "structural_fingerprint": problem.structural_fingerprint,
        "semantic_fingerprint": problem.semantic_fingerprint,
    }
    if uniqueness is not None:
        result["uniqueness_score"] = uniqueness
    return result


def diversity_statistics(problems, split_result=None, split_audit=None):
    problems = tuple(problems)
    distributions = diversity_distributions(problems)
    structural = structural_cluster_report(problems)
    behavior_count = len({problem.behavior_signature for problem in problems})
    unique_ranked = _uniqueness_scores(problems)
    representatives = representative_tasks(problems, 15)
    reskins = []
    for cluster in structural["largest_clusters"]:
        ids = cluster["problem_ids"]
        if len(ids) > 1:
            reskins.append(
                {
                    "structural_fingerprint": cluster["fingerprint"],
                    "problem_ids": ids[:4],
                    "cluster_size": cluster["size"],
                }
            )
        if len(reskins) >= 10:
            break
    non_template = sum(
        problem.generated_program.source_type != "template" for problem in problems
    )
    result = {
        "problem_count": len(problems),
        "distributions": distributions,
        "structural_clusters": structural,
        "behavior_uniqueness": behavior_count / len(problems) if problems else 0.0,
        "behavior_duplicates": len(problems) - behavior_count,
        "reference_verification_fraction": (
            sum(problem.quality.terminating_fraction == 1.0 for problem in problems)
            / len(problems)
            if problems
            else 0.0
        ),
        "non_template_fraction": non_template / len(problems) if problems else 0.0,
        "representative_tasks": [problem_summary(problem) for problem in representatives],
        "most_unique_tasks": [
            problem_summary(problem, score) for score, problem in unique_ranked[:10]
        ],
        "template_reskin_examples": reskins,
    }
    if split_result is not None:
        result["split_sizes"] = {
            name: len(values) for name, values in split_result.as_dict().items()
        }
    if split_audit is not None:
        result["split_audit"] = split_audit
    return result


def diversity_exit_checks(statistics):
    distributions = statistics["distributions"]
    depths = {int(value) for value in distributions["composition_depth"]}
    checks = {
        "count_200_to_500": 200 <= statistics["problem_count"] <= 500,
        "at_least_6_domains": len(distributions["task_domain"]) >= 6,
        "at_least_20_concepts": len(distributions["concepts"]) >= 20,
        "at_least_4_source_types": len(distributions["source_type"]) >= 4,
        "all_composition_depths": {1, 2, 3} <= depths,
        "non_template_at_least_25_percent": statistics["non_template_fraction"] >= 0.25,
        "reference_verification_100_percent": statistics["reference_verification_fraction"] == 1.0,
        "behavior_duplicates_zero": statistics["behavior_duplicates"] == 0,
        "cross_split_leakage_zero": bool(
            statistics.get("split_audit", {}).get("passed", False)
        ),
        "structural_cluster_max_at_most_3": max(
            statistics["structural_clusters"]["cluster_size_distribution"],
            default=0,
        )
        <= 3,
        "at_least_10_reskin_examples": len(
            statistics["template_reskin_examples"]
        )
        >= 10,
    }
    # A category at or above half the data is considered monopolistic.
    for field in ("source_type", "task_domain", "algorithm_family", "template_family"):
        counts = distributions[field]
        maximum = max(counts.values(), default=0)
        checks["balanced_" + field] = maximum / statistics["problem_count"] < 0.5
    concept_maximum = max(distributions["concepts"].values(), default=0)
    checks["balanced_concept"] = (
        concept_maximum / statistics["problem_count"] < 0.5
    )
    checks["passed"] = all(checks.values())
    return checks
