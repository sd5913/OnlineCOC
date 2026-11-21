"""Conservative byte ceilings beneath known or administrator-declared token windows."""
from .errors import require

MAX_REQUEST_BYTES=768*1024
MAX_CAPTURE_BYTES=2*1024*1024
KNOWN_WINDOWS={'deepseek-flash':1048576,'deepseek-v4-pro':1048576}

def budget(profile):
    window=profile['request'].get('contextWindowTokens',KNOWN_WINDOWS.get(profile['model'],65536))
    # UTF-8 serialized bytes conservatively reserve one token per byte. The
    # output and protocol overhead remain outside the input ceiling.
    require(window-profile['request']['maxOutputTokens']>=16384,'CONTEXT_WINDOW_INVALID','The context window must leave at least 16384 tokens after maximum output.')
    ceiling=min(MAX_REQUEST_BYTES,window-profile['request']['maxOutputTokens']-8192)
    return {'contextWindowTokens':window,'inputBytes':ceiling,'requestBytes':ceiling-2048,'compressAtBytes':min(256*1024,int((ceiling-2048)*.75))}
