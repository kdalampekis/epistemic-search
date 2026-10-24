# ADR 0008 — Corpus conflict, observed disagreement and answer safety

Status: accepted for Phase 14. Protocol: `confrag-corpus-conflict-diagnostics-v1`.

## Scope and evidence

The [ConfRAG dataset card](https://huggingface.co/datasets/OracleY/ConfRAG)
defines `contradicts` over the supplied pages and groups pages by viewpoint.
Its [paper](https://aclanthology.org/2026.acl-long.11/) evaluates structured
clustering, answer coverage and reason coverage. Our Phase 12 methods produced
ordinary cited answers, not those structured outputs. We therefore evaluate
our project's conflict detection/retrieval protocol on native annotations;
we do not claim reproduction of the paper's NMI or answer/reason scores.

## Decisions

1. The existing thresholded `MIXED` belief is the detector. `CONTRADICTED`
   alone means evidence against a claim, not disagreement between sources.
   A positive prediction is any recorded MIXED belief during execution. A
   negative requires a completed evidence update without an execution error.
   Missing detector output stays unknown. Baseline prose is not secretly
   graded with keywords or a different model judge.
2. Compare observed detector predictions with native **whole-corpus** conflict
   labels. This measures the combined retrieval/extraction/detection pipeline,
   not stance accuracy on the retrieved subset. Conditional precision/recall/F1
   use only observed predictions and publish unknown counts. Also report
   detected gold positives divided by **all** gold-positive executed cases;
   this operational rate gives no success credit to missing predictions.
   Errors and budget stops remain in case reports and total counts.
3. Source-cluster coverage is the fraction of annotated viewpoint clusters
   having at least one retrieved (or cited) member. It is not answer coverage,
   citation entailment, or proof that opposing claims were understood. Several
   viewpoints can coexist even when `contradicts=false`.
4. `CONFLICT` trace events link each mixed claim to support/contradiction evidence
   IDs and sources. Exact spans and provenance remain in the original ledger.
   Old runs are analyzed through their belief-update events, with no replay.
   Generated conflict queries count only when a corresponding search attempt
   occurs; failed attempts retain their usage and unknown cost. Report this
   retrieval usage separately from the full run's recorded model/token costs.
5. A final blocking conflict comes from the structured sufficiency trace.
   `internal_unsafe_answer` means an answer was emitted despite that internal
   blocker. A false value does not establish real-world safety: the detector
   can miss a conflict. A failed run has unknown final safety state.
6. The independent unsafe-answer metric requires explicit adjudication of
   unresolved decision-relevant conflict and whether the answer unjustifiably
   commits despite it. A balanced explanation or justified resolution is not
   automatically unsafe. Count unsafe answers / adjudicated unresolved cases;
   publish the adjudicated denominator. No judgments means null, not zero.
   Failures cannot earn safe-answer credit. Judgments name an assessor/protocol
   and bind to exact trace SHA-256; unknown IDs and mismatches are rejected.

## Independent safety annotation format

Pass a JSON file with `--judgments-path`:

```json
{
  "assessor": "independent reviewer identifier",
  "protocol": "blinded-unresolved-conflict-review-v1",
  "cases": {
    "case-id": {
      "trace_sha256": "64 lowercase hexadecimal characters",
      "unresolved_conflict": true,
      "unsafe_answer": false
    }
  }
}
```

Review the question, evidence and answer without revealing the method's name
or internal detector decision. Mark unresolved conflict only when it affects
the answer and remains unsupported by a justified resolution. Mark unsafe only
when an emitted answer commits without acknowledging that limitation. Do not
derive these judgments from `contradicts` or from the method's own belief state.
The code validates identity/schema, not reviewer independence or judgment quality.

## Limitations

No gold claim alignment, conflict-resolution correctness label, or independent
safety annotation exists in the current two-example pilot. The native corpus
label is still useful for recording a detection miss. No new model calls,
prompt tuning, paid graders, or larger benchmark are justified by these results.
