"""Measure only the CSV delimiter-probe phase; pandas parsing is stubbed equally.
python scripts/benchmark_csv_probe.py --before /tmp/reader-before.py --after app/services/excel_import/reader.py
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import tracemalloc
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('--before',required=True);p.add_argument('--after',required=True)
args=p.parse_args()
results=[]
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'data.csv'
    with path.open('wb') as f:
        for _ in range(50): f.write(b'a,b\n'*(256*1024))
    for label in ['before','after']:
        spec=importlib.util.spec_from_file_location(label,getattr(args,label))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        frame=pd.DataFrame(columns=['a','b'])
        with patch.object(pd,'read_csv',return_value=frame):
            for repeat in range(5):
                tracemalloc.start()
                start=time.perf_counter()
                module._read_csv_dataframe_from_path(path)
                elapsed=time.perf_counter()-start
                _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                results.append(dict(version=label,repeat=repeat,mib=50,elapsed_ms=elapsed*1000,peak_python_mib=peak/1024**2))
print(json.dumps({'scope':'CSV delimiter probe only; pandas parsing stubbed','samples':results},indent=2))
