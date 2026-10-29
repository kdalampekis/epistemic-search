# RV2-0 status: SUPERSEDED_BEFORE_ANNOTATION

The manual blind spot-check infrastructure in this directory (review packets, selection
manifest, scorer, `annotations/rv2_0/responses.yaml`) was built but **never used**:

* No human RV2-0 labels were collected. `responses.yaml` is the blank template and is
  intentionally left unchanged; it must not be filled in retrospectively.
* No API calls were made for RV2-0.
* On 2026-10-29 the manual validation path was replaced by validation against existing gold
  benchmark annotations. See
  [RV2_EXTERNAL_VALIDATION_PLAN.md](../RV2_EXTERNAL_VALIDATION_PLAN.md).

The files stay as historical work. The RV1 labels remain model-assisted (GPT-5.6 Sol) and
unvalidated by a human; the external-gold RV2 experiments do not change that.
