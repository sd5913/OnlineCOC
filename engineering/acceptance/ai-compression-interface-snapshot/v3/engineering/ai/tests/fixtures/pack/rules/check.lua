return rule('fixture.check', {'actor', 'item'}, function(r, actor, item)
  assert(r.matches(item, 'fixture.token'))
  assert(r.read(actor).owner == r.read(item).owner)
  local charges = r.number(item, 'charges')
  assert(charges > 0, 'No charges remain')
  r.set(item, 'charges', charges - 1)
  local target = math.min(r.readData('tuning.json').maxTarget,
                         r.number(actor, 'target') + r.number(item, 'bonus'))
  local rolled = r.roll(100)
  return {passed=rolled <= target, rolled=rolled, target=target, cost=1}
end)
