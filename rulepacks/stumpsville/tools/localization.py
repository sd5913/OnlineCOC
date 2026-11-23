"""Localize authorized response copies, never saves, user text or full secret catalogs."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def resources():
    source = json.loads((ROOT / 'locales/zh-CN/content.json').read_text(encoding='utf-8'))
    target = json.loads((ROOT / 'locales/en/content.json').read_text(encoding='utf-8'))
    exact = {text: target.get(key, text) for key, text in source.items()}
    patterns = []
    for text, translated in exact.items():
        if '{' in text:
            pattern = re.escape(text)
            for parameter in re.findall(r'\{(\w+)\}', text):
                pattern = pattern.replace(re.escape('{'+parameter+'}'), '(?P<'+parameter+r'>\d+)')
            patterns.append((re.compile(pattern), translated))
    return exact, patterns


def translator(language):
    english = language == 'en' or language.startswith('en-')
    exact, patterns = resources()

    def text(value):
        if not isinstance(value, str):
            return value
        if not english:
            # Only called for generated display strings, never player-authored text.
            if not re.search(r'\b(?:STR|DEX|WIL|HP|XP|Grit)\b', value):
                return value
            if value not in exact and not any(pattern.fullmatch(value) for pattern, _ in patterns) and not re.fullmatch(r'(STR|DEX|WIL|HP|XP|Grit)( 上限)?', value):
                return value
            return re.sub(r'\b(STR|DEX|WIL|HP|XP|Grit)\b',
                          lambda m: {'STR':'力量','DEX':'敏捷','WIL':'意志','HP':'生命','XP':'经验','Grit':'坚韧'}[m[0]], value)
        if value in exact:
            return exact[value]
        title, separator, outcome = value.partition('：')
        if separator and title in exact and outcome in {'已完成', '已结算后果', '条件不满足'}:
            return exact[title] + ': ' + exact.get(outcome, outcome)
        for pattern, translated in patterns:
            match = pattern.fullmatch(value)
            if match:
                return translated.format_map(match.groupdict())
        # These are system-composed item strings, not arbitrary player prose.
        match = re.fullmatch(r'(.+) · 用量 (\d+)', value)
        if match and match[1] in exact:
            return f'{exact[match[1]]} · {match[2]} uses'
        match = re.fullmatch(r'获得(.+)，放入槽位 (\d+)(（超载区）)?。', value)
        if match and match[1] in exact:
            return f'Acquired {exact[match[1]]}, placed in slot {match[2]}' + (' (overflow).' if match[3] else '.')
        for prefix, suffix, translated in [('这里已经没有可领取的','。','No {item} remain here.'),
                                            ('需要一件仍有用量的','。','You need a usable {item}.')]:
            if value.startswith(prefix) and value.endswith(suffix):
                item = value[len(prefix):-len(suffix)]
                if item in exact:
                    return translated.format(item=exact[item])
        return value
    return text


def localize_result(value, language='zh-CN'):
    value = deepcopy(value)
    translate = translator(language)
    def result(data):
        if not isinstance(data, dict):
            return
        for key in ('title', 'message', 'process'):
            if key in data:
                data[key] = translate(data[key])
        if isinstance(data.get('narrative'), list):
            data['narrative'] = [translate(x) for x in data['narrative']]
        for key in ('checks', 'rolls', 'stateChanges'):
            for row in data.get(key, []):
                row['label'] = translate(row['label'])
        for clue in data.get('clues', []):
            for key in ('title', 'text'):
                clue[key] = translate(clue[key])
        if 'result' in data:
            result(data['result'])
    result(value)
    return value


def localize_projection(value, language='zh-CN', *, detached=False):
    data = value if detached else deepcopy(value)
    text = translator(language)
    def fields(row, keys):
        for key in keys:
            if key in row:
                row[key] = text(row[key])
    for location in data.get('locations', []):
        fields(location, ('name', 'description'))
        if 'features' in location:
            location['features'] = [text(x) for x in location['features']]
        for clue in location.get('clues', []):
            fields(clue, ('title', 'text'))
    for item in data.get('items', {}).values():
        fields(item, ('name', 'description'))
    for actor in data.get('mapContacts', []):
        key = actor.pop('nameKey', None)
        if key:
            actor['name'] = text(actor['name'])
    for key in ('sceneActions', 'sceneDefinitions'):
        for action in data.get(key, []):
            fields(action, ('label', 'hint'))
            for choice in action['choices']:
                fields(choice, ('label', 'process'))
    for fact in data.get('sceneStatus', {}).get('facts', []):
        fields(fact, ('label', 'value'))
    for supply in data.get('sceneStatus', {}).get('supplies', []):
        fields(supply, ('name',))
    for rule in data.get('rules', []):
        fields(rule, ('title', 'text'))
    for preset in data.get('presets', []):
        fields(preset, ('description',))
    for task in data.get('autoSceneTasks', []):
        fields(task, ('title',))
    for key in ('events', 'receipts', 'requests'):
        for event in data.get(key, []):
            if key == 'events':
                fields(event, ('title',))
                if event.get('mode') == 'auto':
                    fields(event, ('reason',))
            if 'result' in event:
                event['result'] = localize_result(event['result'], language)
            for change in event.get('changes', []):
                fields(change, ('label', 'before', 'after'))
    for channel in data.get('channels', {}).values():
        if channel.get('kind') == 'scene':
            channel['name'] = text(channel['name'].removeprefix('场景 '))
    return data
