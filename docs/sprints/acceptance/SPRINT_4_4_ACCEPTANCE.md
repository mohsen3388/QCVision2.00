# VisionQC Sprint 4.4 Acceptance

Version: 0.4.4

## Delivered
- Runtime-selectable Factory Blue, Dark, and High Contrast themes.
- Persistent UI scale preference.
- System Health page covering SQLite integrity, writable directories, disk space, and settings availability.
- Offline backup package containing a consistent SQLite snapshot, settings, and versioned manifest.
- Validated restore workflow with automatic pre-restore safety copy.
- Global crash logging to the local VisionQC application-data directory.
- Release documentation and updated Windows installer metadata.

## Safety
- Restore requires explicit operator confirmation.
- Database integrity is checked before replacement.
- Current database is copied before restore.
- No backup or diagnostic data is uploaded automatically.

## Deferred
- Digitally signed Windows binaries and installer.
- Automated online updates.
- Full Persian localization.
- Hardware-in-the-loop Windows certification.
