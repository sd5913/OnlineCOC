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
    request_bytes=ceiling-2048
    # Adapt DeepSeek Harness's pressure/tail policy to our conservative byte
    # meter and smaller application envelope. Never label this as tokenization.
    headroom=min(65536,(window-profile['request']['maxOutputTokens'])//4)
    model_trigger=min(int(window*.8),window-profile['request']['maxOutputTokens']-headroom)
    trigger=min(model_trigger,int(request_bytes*.8))
    return {'contextWindowTokens':window,'inputBytes':ceiling,'requestBytes':request_bytes,
            'compressAtBytes':trigger,'retainBytes':min(int(min(window-profile['request']['maxOutputTokens'],request_bytes)*.16),trigger//2),
            'headroomTokens':headroom,'modelTriggerTokens':model_trigger,'measurement':'conservative-utf8-bytes'}
