from __future__ import annotations
import io, zipfile, urllib.request

URL='https://raw.githubusercontent.com/omnilabNLP/LogicNLI/main/dataset/LogicNLI_sim.zip'
with urllib.request.urlopen(URL, timeout=60) as r:
    data=r.read()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    target='LogicNLI_sim/test_logic.json'
    print('TARGET', target, z.getinfo(target).file_size)
    text=z.read(target).decode('utf-8', errors='replace')
    print(text[:12000])
