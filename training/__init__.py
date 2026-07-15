"""Utilities for building and validating future A=B training data."""

from .jsonl import JsonlError, read_jsonl, read_tasks, write_jsonl, write_tasks
from .generation import (
    BatchGenerationResult,
    FailureReason,
    GeneratedProgram,
    GenerationConfig,
    GenerationExhausted,
    GenerationRejected,
    GenerationStats,
    ProblemGenerator,
    TemplateCatalog,
)
from .dataset import (
    DatasetGenerationResult,
    GeneratedProblem,
    InputPoolConfig,
    ProblemBuildConfig,
    QualityMetrics,
    build_problem,
    generate_dataset,
)
from .prompt import build_prompt
from .reproducibility import (
    ReproducibilityError,
    ReproducibilityResult,
    check_reproducible,
)
from .schema import (
    SchemaValidationError,
    validate_cognitive_task,
    validate_hardened_task,
    validate_task,
)
from .templates import BUILTIN_TEMPLATES, default_template_catalog
from .splitting import LeakageAudit, SplitConfig, SplitResult, audit_leakage, split_problems
from .statistics import quality_statistics
from .baselines import BaselineResult, run_baselines
from .teacher import (
    MockTeacherProvider,
    OpenAICompatibleProvider,
    TeacherCache,
    TeacherPipeline,
    TeacherResult,
    TeacherRoles,
)
from .auxiliary import bounded_trace, generate_auxiliary_tasks
from .diversity import DiversityConfig, diversity_distributions, generate_diversity_smoke
from .diversity_splitting import (
    DiversitySplitResult,
    audit_diversity_splits,
    split_diversity_problems,
)
from .diversity_statistics import diversity_exit_checks, diversity_statistics
from .fingerprints import semantic_fingerprint, structural_fingerprint
from .ir import IROperation, TaskIR, compile_ir, generated_from_ir, verify_ir_oracle
from .mining import behavior_properties, mine_programs
from .novelty import (
    NoveltyScore,
    build_novelty_teacher_prompt,
    novelty_inventory,
    score_novelty,
    verify_teacher_proposal,
)
from .hardening import HardeningConfig, HardeningGenerationResult, generate_hardening_smoke
from .hardening_splitting import (
    HardeningSplitResult,
    audit_hardening_splits,
    split_hardening_problems,
)
from .hardening_statistics import hardening_exit_checks, hardening_statistics
from .cognitive_smoke import (
    audit_cognitive_smoke,
    generate_cognitive_smoke,
    record_cognitive_test_results,
    split_cognitive,
    write_cognitive_smoke,
)

__all__ = [
    "BUILTIN_TEMPLATES",
    "BatchGenerationResult",
    "BaselineResult",
    "DatasetGenerationResult",
    "DiversityConfig",
    "DiversitySplitResult",
    "FailureReason",
    "GeneratedProgram",
    "GeneratedProblem",
    "GenerationConfig",
    "GenerationExhausted",
    "GenerationRejected",
    "GenerationStats",
    "HardeningConfig",
    "HardeningGenerationResult",
    "HardeningSplitResult",
    "JsonlError",
    "IROperation",
    "LeakageAudit",
    "MockTeacherProvider",
    "NoveltyScore",
    "OpenAICompatibleProvider",
    "InputPoolConfig",
    "ProblemBuildConfig",
    "ProblemGenerator",
    "QualityMetrics",
    "ReproducibilityError",
    "ReproducibilityResult",
    "SchemaValidationError",
    "SplitConfig",
    "SplitResult",
    "TemplateCatalog",
    "TeacherCache",
    "TeacherPipeline",
    "TeacherResult",
    "TeacherRoles",
    "TaskIR",
    "audit_leakage",
    "audit_diversity_splits",
    "audit_hardening_splits",
    "audit_cognitive_smoke",
    "behavior_properties",
    "bounded_trace",
    "build_novelty_teacher_prompt",
    "build_prompt",
    "build_problem",
    "check_reproducible",
    "default_template_catalog",
    "diversity_distributions",
    "diversity_exit_checks",
    "diversity_statistics",
    "compile_ir",
    "generate_auxiliary_tasks",
    "generate_dataset",
    "generate_diversity_smoke",
    "generate_hardening_smoke",
    "generate_cognitive_smoke",
    "generated_from_ir",
    "mine_programs",
    "novelty_inventory",
    "quality_statistics",
    "hardening_exit_checks",
    "hardening_statistics",
    "read_jsonl",
    "read_tasks",
    "run_baselines",
    "score_novelty",
    "semantic_fingerprint",
    "split_diversity_problems",
    "split_hardening_problems",
    "split_cognitive",
    "split_problems",
    "structural_fingerprint",
    "validate_task",
    "validate_hardened_task",
    "validate_cognitive_task",
    "verify_ir_oracle",
    "verify_teacher_proposal",
    "write_jsonl",
    "write_tasks",
    "write_cognitive_smoke",
    "record_cognitive_test_results",
]
