import os
from pathlib import Path
import shutil
import sys
import pytest
OUT=Path(__file__).parent
root=OUT/'work/candidate-v4/engineering'
sys.path[:0]=[str(root/p) for p in ('backend/src','data-management','ai/src','ai/tests','backend/tests')]
# Only the percent-encoded path assertion changed after the immutable engine snapshot.
shutil.copy2(OUT.parents[1]/'backend/tests/test_ruling_page_route.py',root/'backend/tests/test_ruling_page_route.py')
os.chdir(root)
raise SystemExit(pytest.main([str(OUT/'test_joint_page.py'),'ai/tests/test_operation_performance.py',
    'backend/tests/test_ruling_page_route.py','-q','-p','no:cacheprovider',
    '--basetemp','../pytest-joint','--junitxml',str(OUT/'joint-v1.xml')]))
