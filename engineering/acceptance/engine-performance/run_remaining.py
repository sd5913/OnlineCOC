"""Finish the interrupted full suite without repeating its 67 successful cases."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
OUT=Path(__file__).parent
args=[sys.executable,'-m','pytest','backend/tests','-q','-x','-p','no:cacheprovider',
      '--basetemp','../pytest-core','--junitxml',str(OUT/'core-v4.xml')]
for case in ET.parse(OUT/'core-v3.xml').iter('testcase'):
    if not any(case.find(tag) is not None for tag in ('failure','error','skipped')):
        args+=['--deselect',case.attrib['classname'].replace('.','/')+'.py::'+case.attrib['name']]
raise SystemExit(subprocess.call(args,cwd=OUT/'work/candidate-v4/engineering'))
