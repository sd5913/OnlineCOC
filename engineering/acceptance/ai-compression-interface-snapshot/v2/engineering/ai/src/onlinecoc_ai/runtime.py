"""Optional local composition; importing Host alone does not start AI work."""
from .pack import Pack
from .profiles import load_profiles
from .proposals import Proposals
from .coordinator import Coordinator
from .context import Context
from .api import Application
import asyncio
from pathlib import Path
import hashlib


class Runtime:
    def __init__(self, host, config_path, pack_path):
        self.config_path = Path(config_path)
        self.config_digest = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
        self.proposals = Proposals(host, Pack(pack_path))
        try:
            self.context = Context(self.proposals, demand=True)
            self.coordinator = Coordinator(self.proposals, load_profiles(config_path), context=self.context)
            self.coordinator.refresh_profiles = self.refresh_profiles
            self.application = Application(self)
            self.watcher = None
            self.auto_error = None
        except BaseException:
            self.proposals.close()
            raise

    def refresh_profiles(self):
        value = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
        if value != self.config_digest:
            profiles = load_profiles(self.config_path)
            self.coordinator.profiles = profiles
            self.config_digest = value

    async def start(self):
        await self.coordinator.start()
        async def watch():
            while True:
                try:
                    scan = asyncio.create_task(asyncio.to_thread(self.application.scan_auto))
                    try:
                        await asyncio.shield(scan)
                        self.auto_error = None
                    except asyncio.CancelledError:
                        try:await scan
                        except Exception:pass
                        raise
                except Exception as exc:
                    # Failed scans never acquire publication permission. Retry
                    # bounded by the next interval and existing source dedup.
                    self.auto_error = getattr(exc, 'code', 'AUTO_SCAN_FAILED')
                await asyncio.sleep(1)
        self.watcher = asyncio.create_task(watch())

    async def close(self):
        try:
            if self.watcher:
                self.watcher.cancel()
                try:await self.watcher
                except asyncio.CancelledError:pass
            await self.coordinator.close()
        finally:
            self.proposals.close()
