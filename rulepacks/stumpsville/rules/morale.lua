return rule('sv.morale', {'actor'}, function(r, actor)
  assert((r.matches(actor, 'sv.npc') or r.number(actor, 'isNpc') == 1), 'SV_NOT_NPC')
  local rolled = r.roll(20)
  local target = r.number(actor, 'wil')
  r.set(actor, 'lastRoll', rolled)
  return {attribute='wil', rolled=rolled, target=target, passed=rolled<=target}
end, {kp=true})
