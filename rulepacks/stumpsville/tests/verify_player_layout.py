"""Resident PL columns, persistent conversation tabs, and draggable notebook."""
from datetime import datetime
import json
import secrets
from harness import PACK, running, provision
from verify_integrations import provider, ai, result
from playwright.sync_api import sync_playwright, expect


def main():
    output=PACK/'tests/output'/('player-layout-'+secrets.token_hex(4));output.mkdir(parents=True)
    checks=[];errors=[]
    with provider(output) as (config,calls), running('player-layout',data=output/'game',ai_config=config,no_browser=True) as (runtime,password):
        kp,p1,p2=provision(runtime,password)
        result(ai(kp,'ai.access.update',{'revision':1,'allowPlayerChat':True,'autoApproveBatches':False}))
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport={'width':1440,'height':900})
            def login(account, player=False):
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(runtime.origin+'/sessions/'+account+'/')
                page.locator('[name=loginName]').fill(account);page.locator('[name=password]').fill(password)
                page.get_by_role('button',name='进入冒险',exact=True).click();page.locator('.identity').wait_for()
                page.goto(runtime.origin+'/sessions/'+account+'/'+('?view=player' if player else '')+'#/play/scene')
                page.locator('.character-column').wait_for()
                return page
            page=login('player1')
            for width,height in [(1920,1080),(1440,900),(1366,768)]:
                page.set_viewport_size({'width':width,'height':height})
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth+1')
                boxes=[page.locator(s).bounding_box() for s in ('.character-column','.scene-column','.communication-column')]
                assert boxes[0]['x']<boxes[1]['x']<boxes[2]['x']
                assert all(b['y']+b['height']<=height+1 for b in boxes)
                expect(page.locator('.resident-status')).to_contain_text('木栗')
                expect(page.locator('.resident-inventory .slot')).to_have_count(10)
            assert not page.locator('.character-tools,[data-action=ai-assistant],.log-column').count()
            checks.append('1920/1440/1366: resident character/inventory, map/actions, and conversation columns fit one viewport without duplicate tools')

            page.locator('#chat-form textarea').fill('聊天草稿保留')
            page.locator('#comm-tab-ai').click()
            editor=page.locator('#player-ai-embedded .reference-editor');editor.wait_for()
            expect(page.locator('#player-ai-embedded .ai-view')).to_have_css('min-height','420px',timeout=15000)
            editor.fill('AI草稿保留')
            page.locator('#comm-tab-chat').click()
            expect(page.locator('#chat-form textarea')).to_have_value('聊天草稿保留')
            p1.action('check',{'attribute':'dex','mode':'normal'})
            page.wait_for_timeout(3000)
            page.locator('#comm-tab-ai').click();expect(editor).to_have_text('AI草稿保留')
            page.locator('#comm-tab-ai').press('ArrowLeft')
            expect(page.locator('#comm-tab-chat')).to_have_attribute('aria-selected','true')
            assert not calls
            checks.append('chat/AI tab switches and state polling retain both drafts; arrow-key tabs work and opening AI does not call a model')

            records=page.locator('[data-action=notebook-toggle][data-args*=records]')
            before=page.locator('.player-notebook').bounding_box();button=records.bounding_box()
            page.mouse.move(button['x']+20,button['y']+12);page.mouse.down()
            page.mouse.move(button['x']+330,button['y']+170,steps=12);page.mouse.up()
            after=page.locator('.player-notebook').bounding_box()
            assert after['x']>before['x']+200 and after['y']>before['y']+100
            expect(records).to_have_attribute('aria-expanded','false')
            records.click();expect(page.locator('#action-feedback')).to_contain_text('敏捷')
            page.locator('.notebook-grip').focus();page.locator('.notebook-grip').press('ArrowRight')
            position=page.locator('.player-notebook').bounding_box()
            page.reload();page.locator('.player-notebook').wait_for()
            restored=page.locator('.player-notebook').bounding_box()
            assert abs(restored['x']-position['x'])<2 and abs(restored['y']-position['y'])<2
            other=login('player2');assert other.locator('.player-notebook').bounding_box()['x']<50;other.close()
            checks.append('notebook buttons and grip drag without accidental toggling; keyboard movement and per-account position/expanded state survive reload')

            page.locator('[data-action=notebook-toggle][data-args*=clues]').click()
            page.locator('#note-form textarea').fill('未保存的线索笔记')
            page.locator('.notebook-grip').press('ArrowDown')
            page.locator('#comm-tab-ai').click();page.locator('#comm-tab-chat').click()
            expect(page.locator('#note-form textarea')).to_have_value('未保存的线索笔记')
            page.locator('#note-form button').click()
            expect(page.locator('#note-form textarea')).to_have_text('未保存的线索笔记')
            page.locator('[data-action=notebook-toggle][data-args*=clues]').click()
            page.locator('.resident-inventory button.slot').first.click();expect(page.locator('#dialog')).to_be_visible()
            page.locator('#dialog [data-action=close]').first.click()
            grip=page.locator('.notebook-grip').bounding_box();top=page.locator('#main').bounding_box()['y']
            page.mouse.move(grip['x']+10,grip['y']+10);page.mouse.down()
            page.mouse.move(35,top+18,steps=12);page.mouse.up()
            page.wait_for_timeout(200)
            page.screenshot(path=str(output/'player-desktop.png'),full_page=True)
            checks.append('clue notes survive dragging and conversation switching, save successfully, and resident inventory opens the real item actions')

            page.set_viewport_size({'width':390,'height':844})
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            page.wait_for_timeout(100)
            rect=page.locator('.player-notebook').bounding_box()
            assert rect['x']>=0 and rect['y']>=0 and rect['x']+rect['width']<=390 and rect['y']+rect['height']<=844
            page.locator('[data-action=notebook-toggle][data-args*=records]').click()
            # A deliberately moved floating control can overlap content; move it
            # back into the reserved top-left space before using mobile tabs.
            grip=page.locator('.notebook-grip').bounding_box()
            top=page.locator('#main').bounding_box()['y']
            page.mouse.move(grip['x']+10,grip['y']+10);page.mouse.down()
            page.mouse.move(30,top+18,steps=12);page.mouse.up()
            for column in ('character','scene','communication'):
                page.locator(f'[data-action=workspace-column][data-args*={column}]').click()
                expect(page.locator('#scene-desktop>.workspace-column:visible')).to_have_count(1)
                assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1 && document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#comm-tab-ai').click();expect(editor).to_be_visible()
            expect(page.locator('#player-ai-embedded .ai-view')).to_have_css('min-height','420px',timeout=15000)
            expect(page.locator('#player-ai-embedded .conversation')).to_have_css('display','flex',timeout=15000)
            page.wait_for_timeout(200)
            page.screenshot(path=str(output/'player-mobile-ai.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':900})
            page.locator('[name=locale]').select_option('en')
            expect(page.locator('#comm-tab-chat')).to_have_text('Chat')
            expect(page.locator('.notebook-grip')).to_have_attribute('aria-label','Drag panel; arrow keys to move')
            own=login('kp',True)
            expect(own.locator('.communication-tabs')).to_be_visible()
            assert not own.locator('.sidebar,#kp-ai-embedded').count()
            checks.append('390px columns and clamped notebook stay reachable; English labels and KP own-player view use the same PL layout')
            browser.close()
    assert not errors,errors
    report={'checkedAt':datetime.now().astimezone().isoformat(),'passed':len(checks),'checks':checks,'consoleErrors':errors,'provider':'loopback; no model calls','realSaveModified':False}
    (PACK/'tests/player-layout-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
