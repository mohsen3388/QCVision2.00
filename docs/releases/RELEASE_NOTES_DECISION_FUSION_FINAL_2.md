# VisionQC Decision Fusion Final 2

- AI review quota gate is now strict: final fused score **80 or higher never invokes cloud AI**.
- Video final score is calculated from the same 12 Quality Pulse indicators shown to the user.
- Temporal scoring uses stable medians and change from the video's opening baseline.
- Reflections, folds, and normal mixing motion no longer create extreme surface/aeration penalties by themselves.
- Final video recommendations are restrained above score 80: continue production and monitor, rather than issuing unconfirmed vacuum/fat-separation actions.
- When AI is not invoked because the score is 80+, the AI tab explicitly states that no review was required.
