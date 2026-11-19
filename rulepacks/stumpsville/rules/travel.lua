return rule('sv.travel', {'actor', 'location:amount'}, function(r, actor, location)
  assert(r.matches(actor, 'sv.character') and r.number(actor, 'approved') == 1, 'SV_NOT_APPROVED')
  local exists = false
  for _, place in ipairs(r.readData('game.json').locations) do
    if place.index == location then exists = true end
  end
  assert(exists, 'SV_LOCATION')
  r.set(actor, 'location', location)
  return {location=location}
end, {kp=true})
