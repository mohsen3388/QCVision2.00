from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
dist = root / "dist" / "VisionQC"
required = [
    dist / "VisionQC.exe",
    dist / "_internal",
    root / "prerequisites" / "VC_redist.x64.exe",
    root / "build_tools" / "VisionQC_Setup.iss",
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("Release verification failed. Missing:")
    print("\n".join(missing))
    sys.exit(1)
exe_size = (dist / "VisionQC.exe").stat().st_size
if exe_size < 1_000_000:
    print("VisionQC.exe is unexpectedly small.")
    sys.exit(1)
print("Release contents verified.")
print("Standalone application:", dist)
print("Bundled Microsoft runtime:", root / "prerequisites" / "VC_redist.x64.exe")
