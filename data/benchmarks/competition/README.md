# Competition Benchmark Data

This directory contains **human annotation templates** for the three
competition evaluation tasks.  All annotation columns are currently **empty**
— status is `pending_annotation`.

## Files

| File | Purpose | Records |
|------|---------|---------|
| `jd_parsing_annotation_template.csv` | JD field extraction ground truth | 100+ sampled real ETL jobs |
| `resume_extraction_annotation_template.csv` | Resume field extraction ground truth | 30 placeholder entries |
| `person_job_matching_annotation_template.csv` | Person-job match labels | 150+ job–resume pairs |
| `annotation_manifest.json` | Manifest with status and protocol | — |

## Annotation Protocol

1. **Two independent annotators** review each record and fill in the
   `annotator_id`, `annotation_date`, and annotation value columns.
2. **Disagreements** are resolved by a third senior reviewer.  Inter-annotator
   agreement is measured with Cohen's kappa; pairs below 0.6 are re-annotated.
3. **Do NOT** use the `machine_*` columns as ground truth — they are rule-based
   references provided only for annotator convenience.

## Task Definitions

### 1. JD Parsing
Annotators read `responsibility` and `requirement` text and extract:
- **Skills**: canonical skill names (pipe-separated), following the taxonomy in
  `scripts/job_taxonomy.py`.
- **Responsibilities**: key responsibility phrases (pipe-separated).
- **Education**: minimum required degree (博士 / 硕士 / 本科 / 大专 / 不限).
- **Experience years**: minimum required years of experience (integer).

### 2. Resume Extraction
Annotators source or create de-identified resumes, then extract:
- **Skills**, **Education**, **Experience years**, **Projects**, **Certifications**.

### 3. Person-Job Matching
Annotators review job–resume pairs and assign:
- **match**: the resume meets all core requirements.
- **partial_match**: the resume meets some but not all core requirements.
- **no_match**: the resume does not meet the core requirements.
- **rationale**: a brief justification for the label.

## Status

**Current status: `pending_annotation`** — no human annotations have been
completed.  The evaluation script (`scripts/evaluate_competition_metrics.py`)
will report `pending_annotation` until all templates have been independently
annotated by at least two reviewers.
