"""Synthetic regression/timing, no emulator or legacy gate measurement."""
import json,statistics,time
from coverage_check import inspect_run
m=dict(schema=1,scenario='synthetic-menu',rom_sha256='a'*64,expected_bp='08001234',min_screenshots=1)
v=dict(manifest=m,rom_sha256='a'*64,textlog='12 BP 00 0 0 08001234 30 BBFF',emulator_log='OK',done=True,screenshot_count=1)
cases=[v,{**v,'textlog':'12 TEXT harmless'},{**v,'rom_sha256':'b'*64},{**v,'done':False},{**v,'screenshot_count':0},{**v,'emulator_log':'FATAL synthetic crash'}]
assert inspect_run(**v)['coverage']=='green'
false_green=sum(inspect_run(**c)['coverage']=='green' for c in cases[1:])
assert false_green==0
times=[]
for _ in range(1000):
 start=time.perf_counter()
 for c in cases: inspect_run(**c)
 times.append((time.perf_counter()-start)*1000)
print(json.dumps(dict(synthetic=True,cases=6,negative_cases=5,illustrative_text_present_baseline_false_green=5,checker_false_green=false_green,median_six_checks_ms=round(statistics.median(times),4),real_pipeline_benchmark=False),sort_keys=True))
