# P1 remediation and verification

## Row-level synchronization

`scripts/bootstrap_storage.py --sync` uses file SHA-256 as a cheap change
detector. When a file changes, MySQL no longer deletes the table. It loads the
source snapshot into a temporary table, compares rows by primary key with
null-safe equality, upserts only inserted or changed rows, and deletes only
target keys absent from the source. Each table merge is transactional. An
exclusive lock prevents concurrent writers, and state JSON is published by
atomic replacement after MySQL and Neo4j complete.

`scripts/sync_mysql_to_es.py` scans Elasticsearch ids and `sync_hash` values,
hashes every MySQL row, indexes only missing or changed documents, and deletes
ids no longer present in MySQL. A changed old record is detected even when its
`collected_at` value is unchanged. `--updated-since` is only a validated
compatibility hint and does not weaken reconciliation correctness.

Neo4j nodes, edges, aliases, trends, and graph versions are aggregate snapshots.
A source change intentionally triggers their full rebuild because one job can
change global counts, weights, trends, and role canonicalisation. This is the
documented full-recomputation boundary; MySQL and Elasticsearch remain row-level.

## Search and benchmarks

Keyword search sorts by `_score` first, then time and id as stable tie-breakers.
Browsing without a keyword sorts by publication time. Four fixed graded query
pools currently produce MRR@10 1.0000 and nDCG@10 0.9315. They have one reviewer
and unjudged results count as irrelevant, so this is a regression baseline, not
a general relevance claim.

The independent fixed holdout has 24 manually reviewed natural-language cases
across eleven strata. Current results are skill F1 0.8125 and category accuracy
0.6667. These deliberately non-perfect values expose known rule gaps. The set
has one reviewer and is not double-blind; a production claim requires a larger
domain sample and two independent annotators.

## Clean-room initialization

Compose container names and host ports are parameterised while retaining the
existing defaults. `scripts/verify-cleanroom.ps1` creates a unique Compose
project with free local ports and fresh volumes, loads all three stores, checks
the 55,110-row invariant, and always removes its isolated resources.

The verified clean-room run loaded 55,110 jobs, 69,291 skill evidence rows,
907 nodes, 1,806 edges, 2,932 trends, 22 graph versions, and indexed 55,110
Elasticsearch documents. The alias CSV contains 34,094 input rows. MySQL's
case-insensitive `utf8mb4_unicode_ci` composite key stores 33,998 distinct
`(alias, canonical_role_id)` rows, so staging deterministically upserts the 96
case-only variants; Neo4j preserves all 34,094 case-sensitive alias ids. The
temporary containers, network, and volumes were then removed successfully.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-cleanroom.ps1
```
