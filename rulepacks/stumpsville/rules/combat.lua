-- One exchange is one host transaction, including the enemy response and release.
return rule('sv.combat', {'actor','enemy:actor','operation:text','battle:amount','turn:amount','enemyDie:amount','counterAttribute:text'}, function(r, actor, enemy, operation, key, turn, enemyDie, counterAttribute)
  assert(r.matches(actor,'sv.character') and (r.matches(enemy,'sv.npc') or r.number(enemy,'isNpc')==1),'SV_COMBAT_TARGET')
  local session=r.related(actor,'source')[1]
  assert(session and r.number(session,'phase')==1 and r.number(actor,'approved')==1 and r.number(actor,'ready')==1,'SV_NOT_READY')
  assert(key>0 and (enemyDie==4 or enemyDie==6 or enemyDie==8 or enemyDie==10 or enemyDie==12),'SV_COMBAT_INPUT')
  local function number(id,field) return r.read(id).numbers[field] or 0 end
  local function down(id) return number(id,'incapacitated')>0 or number(id,'str')<=0 or number(id,'dex')<=0 or number(id,'wil')<=0 end
  assert(counterAttribute=='str' or counterAttribute=='dex','SV_COMBAT_INPUT')
  local membership=number(actor,'combatKey')
  assert(turn==number(actor,'combatTurn'),'SV_COMBAT_STALE')
  local out={outcome='active'}
  if operation=='engage' then
    assert(membership==0 and not down(actor) and not down(enemy) and number(actor,'location')==number(enemy,'location'),'SV_COMBAT_UNAVAILABLE')
    r.set(actor,'combatKey',key)
  else
    assert(membership==key and number(enemy,'combatKey')==key,'SV_COMBAT_STALE')
    assert(operation=='attack' or operation=='flee','SV_COMBAT_INPUT')
    if down(actor) then out.outcome='incapacitated'
    elseif not down(enemy) then
      if operation=='flee' then
        out.check=r.call('sv.check.core',actor,'dex','normal')
        if out.check.passed then out.outcome='escaped' end
      else
        local sides=4
        for slot=1,2 do
          local def=r.readData('game.json').items[number(actor,'item'..slot)]
          if def and def.kind=='weapon' and number(actor,'uses'..slot)>0 then
            local dice={d4=4,d6=6,d8=8,d10=10,d12=12}
            sides=math.max(sides,dice[def.damage] or 4)
          end
        end
        out.attackRoll=r.roll(sides)
        out.attack=r.call('sv.damage',enemy,out.attackRoll,'str')
      end
      if not down(enemy) and out.outcome=='active' then
        out.counterRoll=r.roll(enemyDie)
        out.counter=r.call('sv.damage',actor,out.counterRoll,counterAttribute)
        if down(actor) then out.outcome='incapacitated' end
      end
    end
    if down(enemy) then
      out.outcome='victory'
      for _,ally in ipairs(r.related(session,'references')) do
        if r.matches(ally,'sv.character') and number(ally,'combatKey')==key then r.set(ally,'combatKey',0) end
      end
    end
    if out.outcome~='active' then r.set(actor,'combatKey',0) end
  end
  r.set(enemy,'combatKey',key)
  r.set(actor,'combatTurn',turn+1)
  out.enemyHp=number(enemy,'hp')
  out.enemyMaxHp=number(enemy,'maxHp')
  return out
end,{kp=true,dependencies={'sv.damage','sv.check.core'}})
