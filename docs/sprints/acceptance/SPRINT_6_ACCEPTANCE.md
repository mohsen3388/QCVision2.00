# VisionQC Sprint 6 Acceptance — Version 0.6.0

## Goal
Introduce offline Statistical Process Control (SPC) so factories can persist quality measurements, visualize process behaviour, distinguish control limits from specification limits, and assess basic process capability.

## Delivered
- `quality_measurements` SQLite table and metric/time index.
- Manual measurement capture linked optionally to a batch, product, line and operator.
- X-style control chart with center line, UCL/LCL and LSL/USL.
- Mean, sample sigma, Cp and Cpk calculations.
- Out-of-control and out-of-specification detection.
- Explainable trend checks: seven increasing/decreasing points and eight points on one side of center.
- Measurement history table and CSV export.
- New **Statistical Process Control** page in the sidebar and **☰ ALL FEATURES** catalog.

## Safety boundary
SPC is decision support. Control limits are calculated from available samples and do not replace a validated sampling plan, MSA/Gage R&R, laboratory testing, process engineering approval or qualified QC release.

## Deferred
- X-bar/R subgroup charts, p/np/c/u charts.
- Automated import from image/video analyses.
- MSA and Gage R&R.
- Shift definitions and OEE.
- Signed management PDF reports.
