# 04 · NLP classification (AG News): technical review

## Verdict
A careful routing study, but the headline cascade gain (+0.001 macro-F1 on 1,000 fresh items) is inside sampling noise and must not be presented as an improvement. Fix the claim before anything else.

## Architecture
- Ladder: majority, uniform, TF-IDF + logistic, roberta-base, DistilBERT default and tuned, DistilBERT full 120k, and an int8 variant. A sensible cost-quality ladder.
- Selective LLM cascade: transformer answers when confident (τ=0.6), and only low-confidence rows go to the LLM in 8-row batches. This is a sound design.

## Results vs benchmarks and SOTA
- Full-data DistilBERT reaches 0.946 accuracy on the bounded test. Published AG News results for strong encoders sit around 95 percent (**verify** the exact citation and split before quoting).
- The chosen baseline set is appropriate. A stronger public reference would be a larger encoder; the card should say the ladder stops at DistilBERT by design.

## Metrics and statistics
- **Blocker.** Cascade on the fresh 1,000: 0.9529432 → 0.9539265 macro-F1, 22 reviews. The difference is about 1 item. Without a paired bootstrap CI, this is not an improvement. Report it as "no measurable change" unless a paired test shows otherwise.
- Three splits (validation, bounded test, fresh) show different absolute values. Each row should name its split in the same column.
- The int8 row reports quality on a 2,000-row train sample, while other rows report the 1,000-row test. That is not comparable. Either measure int8 on the same test split or put the two in separate tables.
- Accuracy and macro-F1 for the same run differ by less than 0.001. Fine, but state that the split is balanced (250 per class), so the two agree by construction.

## Code and tests
- 16 test files. Add a test that the cascade's reviewed count matches the number of rows below τ.

## Visuals
- `llm_cascade_comparison` should show the paired difference with its interval, not two bars that look different.
- `confusion_matrix_selected` is appropriate.

## Copy and articles
- short_version uses 0.9529432 and 0.9539265. Round to 0.953 → 0.954 (repo convention) and keep the full values in the table.
- "License unknown" in copy: state the dataset licence or drop the line.
- Cost "$0.023671 cloud-equivalent" is a declared rate card; name the rate in the copy.

## Kimi refinement tasks
1. (blocker) Replace the cascade-gain claim with a paired bootstrap interval on the fresh split, and reword to "no measurable change" if the interval includes zero.
2. (major) Make the int8 row comparable: same test split, same metric.
3. (major) Add a test asserting the cascade reviews exactly the rows below τ.
4. (minor) Round the headline numbers in short_version; state the cost rate card in copy.
5. (minor) Resolve the "License unknown" line.
