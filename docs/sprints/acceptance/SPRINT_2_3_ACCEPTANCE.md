# Sprint 2.3 Acceptance Checklist

- [x] ALL FEATURES menu remains visible and shows every product capability.
- [x] Video Analysis is marked AVAILABLE and opens a working page.
- [x] User can select common video formats.
- [x] User can configure the frame sampling interval.
- [x] Video processing runs in a worker thread.
- [x] User can request cancellation.
- [x] Frame-level temporal samples are displayed.
- [x] Overall health, confidence and process stability are calculated.
- [x] Temporal events are derived from status and metric changes.
- [x] Timeline chart is displayed without extra plotting dependencies.
- [x] Evidence snapshots are retained.
- [x] Temporal result can be exported as JSON.
- [x] USB camera page supports camera index, probe, live preview and stop.
- [x] Phone/IP page validates RTSP/HTTP URLs and probes the source.
- [x] Live monitoring performs periodic analysis and shows a rolling timeline.
- [x] Camera resources are released on stop/application close.
- [x] End-user Windows installer workflow remains documented.

## Validation still required on the target Windows computer

- [ ] Visual inspection of all PySide6 pages.
- [ ] USB camera test with the user's physical webcam.
- [ ] RTSP/HTTP test with the selected phone app or IP camera.
- [ ] Long-duration camera stability test.
- [ ] Build and smoke-test the generated Setup.exe.
