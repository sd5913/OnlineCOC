"""Explicit new-room initialization; ordinary startup never calls this operation."""
import copy

from .access import DEFAULT_POLICY
from .errors import require


def initialize(app, account, args):
    with app.host.lock, app.lock:
        app.host.kp(account)
        recover(app)
        room = app.host.state()
        require(args['scopeId'] == room['aiControl']['scopeId'], 'SCOPE_MISMATCH')
        state = app.repository.state()
        marker = state['settings'].get('roomDefaults')
        if marker:
            return {**marker, 'initialized': False, 'settings': copy.deepcopy(room['aiControl']['settings'])}
        # Explicit setup alone may seed defaults. Never overwrite a used or
        # customized AI store, including a room predating this feature.
        require(not any(state[k] for k in ('requests', 'proposals', 'contexts', 'memory', 'tasks', 'budgets')) and
            not any(k in state['settings'] for k in ('accessPolicy', 'sessions', 'autoPositions', 'cReviewBasis')),
            'ROOM_ALREADY_CONFIGURED')
        require(all(c.get('op') == 'ai.room.initialize' for c in state['commands'].values()), 'ROOM_ALREADY_CONFIGURED')
        current = room['aiControl']['settings']
        require(not current['enabled'] and not current.get('profileId') and
            not current['externalSources'].get('private') and not current['externalSources'].get('kp') and
            not current['auto']['enabled'], 'ROOM_ALREADY_CONFIGURED')
        if hasattr(app.runtime, 'refresh_profiles'):app.runtime.refresh_profiles()
        profiles = app.coordinator.profiles
        enabled = [key for key, p in profiles.items() if p['enabled']]
        selected = args.get('profileId')
        if selected is not None:
            require(selected in profiles, 'PROFILE_NOT_FOUND')
            require(profiles[selected]['enabled'], 'PROFILE_DISABLED')
        elif len(enabled) == 1:selected = enabled[0]
        target = {**copy.deepcopy(current), 'enabled': selected is not None, 'profileId': selected,
            'externalSources': {'public': True, 'private': True, 'kp': True}}
        policy = {**DEFAULT_POLICY, 'allowPlayerChat': True, 'principal': account}
        marker = {'scopeId': args['scopeId'], 'initializedBy': account, 'initializedAt': app.host.clock(),
            'serviceStatus': 'ready' if selected else 'profile_selection_required' if enabled else 'profile_unavailable'}
        # The durable intent permits conservative recovery after a host commit.
        # Retrying initialization after a later settings edit never resets it.
        def save(data):
            data['settings']['accessPolicy'] = policy
            data['settings']['roomDefaults'] = {**marker, 'pendingSettings': target}
        app.repository.update(save)
        room['aiControl']['settings'] = target
        app.host.commit(room)
        app.repository.update(lambda s: s['settings']['roomDefaults'].pop('pendingSettings', None))
        return {**marker, 'initialized': True, 'settings': copy.deepcopy(target)}


def recover(app):
    with app.host.lock:
        marker = app.repository.state()['settings'].get('roomDefaults', {})
        if 'pendingSettings' not in marker:return
        room = app.host.state()
        require(marker['scopeId'] == room['aiControl']['scopeId'], 'SCOPE_MISMATCH')
        room['aiControl']['settings'] = copy.deepcopy(marker['pendingSettings'])
        app.host.commit(room)
        app.repository.update(lambda s: s['settings']['roomDefaults'].pop('pendingSettings', None))
