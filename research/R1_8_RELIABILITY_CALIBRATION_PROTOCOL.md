# R1.8 Reliability Certificate Calibration Protocol

Date: 2026-08-13
Parent checkpoint: `Nolane-R1.8-CCSM-ConditionalLaw.pt` SHA `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`.
Benchmark: FIGG-18 v1, **train only**.

Calibration worlds: indices `32..47` inclusive for each of the four FIGG-18 families (64 worlds total). These worlds are disjoint from conditional-law fit `0..23` and internal-validation `24..31`.

Certificate score is fixed before calibration:
`seen_evidence * consistency * context_similarity * exp(-32 * model_memory_mse)`.

Threshold candidates: `{0.5, 0.6, 0.7, 0.8, 0.9}`.
A certified action prediction is empirically safe when its structured-effect MSE to the train simulator target is `<=0.005`.

Acceptance rule:
1. certified precision >=95% overall;
2. certified precision >=95% in every FIGG-18 family;
3. among passing thresholds choose maximum coverage; ties choose the higher/safer threshold;
4. if no threshold passes, reliability certification is rejected and no dev gate may use model-based planning.

This calibration does not update neural weights. FIGG-18 dev/fresh remain unopened.
