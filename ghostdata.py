import sys
sys.dont_write_bytecode = True
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
from ghostdata.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
