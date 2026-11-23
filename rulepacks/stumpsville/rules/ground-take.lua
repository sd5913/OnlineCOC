return rule('sv.ground.take', {'actor', 'slot:amount', 'item:amount', 'uses:amount', 'ticks:amount', 'location:amount'}, function(r, actor, slot, item, uses, ticks, location)
  assert(r.number(actor, 'location') == location, 'SV_SCENE_LOCATION')
  local result = r.call('sv.grant', actor, item, slot, uses)
  r.set(actor, 'ticks' .. slot, ticks)
  return result
end, {kp=true, dependencies={'sv.grant'}})
