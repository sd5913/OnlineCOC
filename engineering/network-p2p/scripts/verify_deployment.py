"""Read-only checks of the configured deployment; private configuration stays local."""
import asyncio
import contextlib
import json
import ssl
from pathlib import Path
from urllib.parse import urlsplit

from onlinecoc_p2p.common import Fault,atomic_json
from onlinecoc_p2p.control import Control


async def main():
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/"local/client-config.json").read_text(encoding="utf-8"))
    control=Control(config["directory"],config["caFile"])
    try:
        assert (await control.request("GET","/health"))["status"]=="ok"
        try:
            await control.request("POST","/v1/rooms","incorrect",{})
            raise AssertionError("Publisher accepted without credentials")
        except Fault as error:
            assert error.code=="PUBLISHER_AUTH_REQUIRED"
        host=urlsplit(config["directory"]).hostname
        _,writer=await asyncio.wait_for(asyncio.open_connection(host,5349,
            ssl=ssl.create_default_context(cafile=config["caFile"]),server_hostname=host),10)
        ssl_object=writer.get_extra_info("ssl_object")
        version=ssl_object.version()
        writer.close()
        with contextlib.suppress(ConnectionResetError):
            await writer.wait_closed()
        atomic_json(root/"local/acceptance/deployment-health.json",
            {"httpsHealth":True,"publisherAuthRequired":True,"turnTlsHandshake":version,
             "turnTlsDataChannel":"not advertised to default browser clients; not part of the UDP/TCP data-channel acceptance",
             "certificateValidation":True})
        print("HTTPS health, publisher authorization and certificate-verified TURN TLS listener passed")
    finally:
        await control.close()


if __name__=="__main__":
    asyncio.run(main())
