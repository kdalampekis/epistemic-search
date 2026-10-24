# ADR 0017 — Paper artifacts from validated saved results

Status: accepted for Phase 23.

Reuse the Phase 20 analysis function with an optional output destination. Its
scoring, resampling and paired-test logic stay unchanged. Generate each dataset
separately and keep scripted ablations explicitly labelled. The paper generator
validates complete scores and trace identity/usage, then records input and output
hashes. No numbers are manually transcribed and no model provider is invoked.

Tables use CSV (full precision), Markdown and escaped LaTeX. Optional Matplotlib
produces SVG/PDF/PNG; fixed SVG salt and omitted timestamp metadata make repeated
exports identical in the same locked environment. Matplotlib's savefig metadata
interface is documented at https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html.
Plot byte identity across platforms/font libraries is not guaranteed.

Select one minimum seeded hash per group/outcome across methods, retaining the
entire population and selection decisions in an inventory. These are illustrative
outcome-stratified excerpts, not a representative causal analysis or hand-picked
success stories. Unavailable scores stay NA/null; errors retain their original
scores. Physical cost and latency reflect cache reuse. All-or-nothing staging
avoids publishing a partial artifact set when validation fails.
