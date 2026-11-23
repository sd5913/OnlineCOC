"""Explicit administrator-installed local data adapter, never model-selected."""
import importlib.util
import hashlib
from pathlib import Path
from .errors import require


def install(host, module_path, data_path):
    path=Path(module_path).resolve(strict=True)
    require(path.suffix=='.py','INPUT_INVALID')
    spec=importlib.util.spec_from_file_location('onlinecoc_installed_data_adapter',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter=module.create_adapter(Path(data_path).resolve())
    require(callable(getattr(adapter,'read',None)),'INPUT_INVALID')
    host.ai_data_adapter=adapter
    host.ai_data_adapter_digest=hashlib.sha256(path.read_bytes()).hexdigest()
