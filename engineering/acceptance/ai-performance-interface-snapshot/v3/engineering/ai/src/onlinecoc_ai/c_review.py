"""KP-owned, versioned gameplay evidence. This never relaxes A/B or execution checks."""
import copy

from .contracts import canonical, digest, validate
from .errors import require


ADOPTABLE_CODES = frozenset({'EXTENSION_FORBIDDEN', 'LIVE_SCENARIO_COVERAGE_MISSING', 'EXISTING_INSTANCE_COVERAGE_MISSING'})
DEFAULT = {'revision': 1, 'metricOverrides': {}, 'liveScenarios': [], 'notes': ''}


def basis(repository):
    return copy.deepcopy(repository.read_state()['settings'].get('cReviewBasis', DEFAULT))


def basis_binding(value):
    return {'basisRevision': value['revision'], 'basisDigest': digest(value)}


def detached_resolver(repository,scope_id):
    """Reopen persisted evidence after service shutdown; never trust a cached basis."""
    from .segmented_store import SegmentedStore
    from onlinecoc.errors import DomainError
    path=getattr(repository.store,'path',None)
    def resolve():
        store=None
        try:
            if path is not None:
                require(path.is_dir(),'C_BASIS_UNAVAILABLE')
                store=SegmentedStore(path)
                state=store.snapshot()[1]
            else:state=repository.store.snapshot()[1]
            require(state and state.get('scopeId')==scope_id,'C_BASIS_UNAVAILABLE')
            value=state['settings'].get('cReviewBasis',DEFAULT)
            validate('CReviewBasis',value)
            return basis_binding(value)
        except Exception as exc:
            raise DomainError('C_BASIS_UNAVAILABLE') from exc
        finally:
            if store is not None:store.close()
    return resolve


def assessment(reports, value):
    levels = {r['level']: r for r in reports}
    c = levels.get('C', {})
    errors = [f for f in c.get('findings', []) if f['severity'] == 'error']
    allowed = (len(reports) == 3 and set(levels) == {'A', 'B', 'C'} and
        all(levels[k]['status'] == 'pass' and not any(f['severity']=='error' for f in levels[k].get('findings',[])) for k in ('A', 'B')) and
        (c.get('status') == 'pass' and not errors or c.get('status') == 'unknown' and
         bool(errors) and all(f['code'] in ADOPTABLE_CODES for f in errors)))
    return {**basis_binding(value), 'reportDigest': digest(reports), 'adoptable': bool(allowed),
        'requiresAcceptance': c.get('status') != 'pass'}


def update(app, account, args):
    with app.host.lock:
        app.host.kp(account)
        previous = basis(app.repository)
        require(args['revision'] == previous['revision'], 'C_BASIS_VERSION_CONFLICT')
        require(set(args['metricOverrides']) <= {m['metricId'] for m in app.proposals.pack.metrics}, 'C_METRIC_NOT_FOUND')
        require(len(canonical(args)) <= 32768, 'C_BASIS_TOO_LARGE')
        value = {**copy.deepcopy(args), 'revision': previous['revision'] + 1}
        validate('CReviewBasis', value)
        def save(state):
            require(basis(app.repository)['revision'] == previous['revision'], 'C_BASIS_VERSION_CONFLICT')
            state['settings']['cReviewBasis'] = value
            state['settings'].setdefault('cReviewBasisHistory', []).append({
                'basis': value, 'previousDigest': digest(previous), 'changedBy': account, 'changedAt': app.host.clock()})
            return {**value, **basis_binding(value)}
        return app.repository.update(save)


def settings(app):
    value = basis(app.repository)
    return {**value, **basis_binding(value), 'metrics': copy.deepcopy(app.proposals.pack.metrics),
        'authorLiveScenarios': copy.deepcopy(app.proposals.pack.json(app.proposals.pack.contract['contextMapping']['liveScenarios']))
            if app.proposals.pack.contract['contextMapping'].get('liveScenarios') else [],
        'adoptableCodes': sorted(ADOPTABLE_CODES)}
