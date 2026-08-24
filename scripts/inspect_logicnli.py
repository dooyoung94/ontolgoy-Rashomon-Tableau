from __future__ import annotations
import io, zipfile, urllib.request

URL='https://raw.githubusercontent.com/omnilabNLP/LogicNLI/main/dataset/LogicNLI_sim.zip'
with urllib.request.urlopen(URL, timeout=60) as r:
    data=r.read()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    print('FILES')
    for name in z.namelist():
        info=z.getinfo(name)
        print(name, info.file_size)
    print('\nSAMPLES')
    for name in z.namelist():
        if name.endswith('/') or z.getinfo(name).file_size > 5_000_000:
            continue
        if any(name.lower().endswith(ext) for ext in ('.json','.jsonl','.txt','.csv','.tsv')):
            try:
                text=z.read(name).decode('utf-8', errors='replace')
                print(f'--- {name} ---')
                print(text[:3000])
            except Exception as e:
                print(name, 'ERR', repr(e))
            if name.lower().endswith(('.json','.jsonl')):
                break
