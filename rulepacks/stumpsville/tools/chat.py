"""Package-scoped scene/team chat. Host still owns global and direct channels."""
import time
import copy


class ScopedChat:
    def __init__(self, package):
        self.package = package
        self.data = package.state['scopedChat']

    def channels(self, view):
        p = self.package
        account = view['accountId']
        characters = p.entities(view, 'sv.character')
        mine = next((c for c in characters if c['owner'] == account), None)
        locations = {c['numbers']['location'] for c in characters} if view['role'] == 'kp' else ({mine['numbers']['location']} if mine else set())
        ids = {'sv-scene-'+str(n): '场景 '+str(n) for n in locations}
        if mine or view['role'] == 'kp':
            ids['sv-party'] = '队伍'
        result = {}
        for key, name in ids.items():
            messages = self.data['messages'].get(key, [])
            read = self.data['reads'].get(account, {}).get(key, 0)
            result[key] = {'channelId': key, 'kind': 'scene' if key.startswith('sv-scene-') else 'party',
                'name': name, 'canPost': view['status'] != 'archived', 'revision': sum(m['revision'] for m in messages),
                'lastSequence': messages[-1]['sequence'] if messages else 0, 'readSequence': read,
                'unreadCount': sum(m['sequence'] > read and m['senderAccountId'] != account and not m['deleted'] for m in messages)}
        return result

    def projection(self, client, player_mode=False):
        # Host authorization and network I/O do not occupy the package write lock.
        view = client.request('/view')
        with self.package.lock:
            return {'accountId': view['accountId'], 'channels': {
                **view['chatChannels'], **self.channels({**view, 'role': 'player'} if player_mode else view)}}

    def history(self, client, args):
        if not isinstance(args, dict):
            raise ValueError('INVALID_CHAT_PAGE')
        channel = args.get('channelId')
        if not str(channel).startswith('sv-'):
            return client.request('/chat/history', args)
        view = client.request('/view')
        with self.package.lock:
            return self.scoped_history(view, args)

    def scoped_history(self, view, args):
        channel = args.get('channelId')
        channels = self.channels(view)
        if channel not in channels:
            raise ValueError('NOT_VISIBLE')
        before = args.get('before', 2**53)
        limit = args.get('limit', 50)
        if type(before) is not int or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('INVALID_CHAT_PAGE')
        messages = [m for m in self.data['messages'].get(channel, []) if m['sequence'] < before]
        items = messages[-limit:]
        return {'items': copy.deepcopy(items), 'channelRevision': channels[channel]['revision'],
                'lastSequence': channels[channel]['lastSequence'], 'nextBefore': items[0]['sequence'] if len(messages) > limit else None}

    def action(self, view, operation, args, action_id):
        channel = args.get('channelId')
        channels = self.channels(view)
        if channel not in channels:
            raise ValueError('NOT_VISIBLE')
        account = view['accountId']
        messages = self.data['messages'].setdefault(channel, [])
        if operation == 'chat.read':
            seq = args.get('sequence')
            if type(seq) is not int or not 0 <= seq <= channels[channel]['lastSequence']:
                raise ValueError('INVALID_READ_POSITION')
            reads = self.data['reads'].setdefault(account, {})
            reads[channel] = max(seq, reads.get(channel, 0))
            return {'channelId': channel, 'readSequence': reads[channel]}
        if not channels[channel]['canPost']:
            raise ValueError('ROOM_ARCHIVED')
        if operation in {'chat.message.send', 'chat.message.edit'}:
            text = args.get('text')
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise ValueError('消息应为1–4000个字符')
        if operation == 'chat.message.send':
            prior = next((m for m in messages if m['messageId'] == action_id), None)
            if prior:
                return {'channelId': channel, 'messageId': action_id, 'sequence': prior['sequence']}
            if len(messages) >= 10000:
                raise ValueError('本频道已达10000条记录上限')
            message = {'messageId': action_id, 'channelId': channel, 'sequence': len(messages)+1, 'revision': 1,
                       'senderAccountId': account, 'speakerName': None, 'createdAt': time.time(), 'text': text, 'deleted': False}
            messages.append(message)
            return {'channelId': channel, 'messageId': action_id, 'sequence': message['sequence']}
        message = next((m for m in messages if m['messageId'] == args.get('messageId')), None)
        if not message or (message['senderAccountId'] != account and not (view['role'] == 'kp' and operation == 'chat.message.retract')):
            raise ValueError('NOT_VISIBLE')
        if message['revision'] != args.get('revision') or message['deleted']:
            raise ValueError('VERSION_CONFLICT')
        if operation not in {'chat.message.edit', 'chat.message.retract'}:
            raise ValueError('聊天操作不支持')
        message.update(text=text if operation == 'chat.message.edit' else '', deleted=operation == 'chat.message.retract',
                       revision=message['revision']+1, updatedAt=time.time())
        return {'channelId': channel, 'messageId': message['messageId'], 'revision': message['revision']}
