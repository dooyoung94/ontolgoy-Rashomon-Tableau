from __future__ import annotations
import argparse, subprocess
from pathlib import Path

URL="https://github.com/BLPXSPG/Conan.git"

def main():
    p=argparse.ArgumentParser(); p.add_argument("--dest",default="data/conan"); p.add_argument("--force",action="store_true"); a=p.parse_args()
    dest=Path(a.dest)
    if dest.exists() and a.force:
        import shutil; shutil.rmtree(dest)
    if dest.exists():
        print(f"[skip] {dest} already exists"); return
    dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["git","clone","--depth","1",URL,str(dest)],check=True)
    print(f"[ok] Conan downloaded to {dest}")

if __name__=="__main__": main()
