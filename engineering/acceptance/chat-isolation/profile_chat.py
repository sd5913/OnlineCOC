from pathlib import Path
import cProfile,pstats,sys,time,json
HERE=Path(__file__).resolve().parent;root=HERE/'work'/'after'/'engineering'
for p in ('backend/src','data-management','ai/src'):sys.path.insert(0,str(root/p))
from fixture import setup,message
h,service,approval=setup(root,HERE/'work'/('profile-'+str(time.time_ns())),stable=True)
try:
 out=[]
 for n in range(5):
  if n:
   r=h.command('kp',message(h,'kp','ai.proposal.approve',approval));assert r['status']=='committed',r
  prof=cProfile.Profile();prof.enable()
  r=h.command('player1',message(h,'player1','chat.message.send',{'channelId':'general','text':'profile'}))
  prof.disable();assert r['status']=='committed',r
  with (HERE/f'profile-{n}.txt').open('w') as f:pstats.Stats(prof,stream=f).strip_dirs().sort_stats('cumtime').print_stats(20)
  import onlinecoc.contracts as contracts
  out.append({'approvals':n,'commitMs':h.metrics['commits'][-1],'cacheEntries':len(contracts._APPROVAL_VALIDATED)})
 print(json.dumps(out))
finally:service.close();h.close()
