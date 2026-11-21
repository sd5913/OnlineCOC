import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"backend/src"),str(ROOT/"data-management"),str(ROOT/"ai/src")]
if __name__=="__main__":
    from onlinecoc.cli import main
    from onlinecoc.errors import DomainError
    try:
        main()
    except DomainError as exc:
        import json
        result = {'code': exc.code}
        if exc.code == 'SCHEMA_UNSUPPORTED' or isinstance(exc.detail, dict):
            result['detail'] = exc.detail
        print(json.dumps(result, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(2)
