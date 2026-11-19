"""Named room directories for the package panel; never converts existing saves."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import uuid


class RoomSlots:
    def __init__(self, root):
        self.root = Path(root).resolve()
        engine = Path(__file__).resolve().parents[3] / 'engineering'
        if self.root.is_relative_to(engine):
            raise ValueError('房间数据应位于 engineering 目录外。')
        self.directory = self.root / 'slots'

    def path(self, slot_id):
        if not isinstance(slot_id, str) or not re.fullmatch(r'[a-f0-9]{32}', slot_id):
            raise ValueError('无效房间槽位。')
        path = self.directory / slot_id
        # Do not follow a substituted slot or slots-directory junction.
        if self.directory.resolve() != self.directory or path.resolve() != path:
            raise ValueError('房间槽位不能使用符号链接或目录联接。')
        return path

    def list(self):
        rows = []
        if self.directory.resolve() != self.directory:
            raise ValueError('房间槽位目录不能使用符号链接或目录联接。')
        if not self.directory.exists():
            return rows
        for path in sorted(self.directory.iterdir()):
            if not re.fullmatch(r'[a-f0-9]{32}', path.name):
                continue
            path = self.path(path.name)
            try:
                value = json.loads((path/'slot.json').read_text(encoding='utf-8'))
                if value.get('format') != 1 or value.get('id') != path.name:
                    raise ValueError()
                self.validate_name(value.get('name'))
            except (OSError, ValueError, AttributeError) as error:
                raise ValueError('槽位信息无法读取：'+path.name+'；请检查 slot.json，现有房间数据未改动。') from error
            rows.append(value)
        return sorted(rows, key=lambda row: (row['createdAt'], row['id']))

    def selected(self):
        rows = self.list()
        try:
            selected = json.loads((self.root/'slot-selection.json').read_text(encoding='utf-8')).get('selected')
        except (OSError, ValueError, AttributeError):
            selected = None
        return next((row for row in rows if row['id'] == selected), rows[0] if rows else None)

    @staticmethod
    def validate_name(name):
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(c) < 32 for c in name):
            raise ValueError('槽位名称需为1–40个字符，不能包含换行。')
        return name.strip()

    @staticmethod
    def write(path, value):
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as file:
                json.dump(value, file, ensure_ascii=False, indent=2)
                file.write('\n');file.flush();os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def select(self, slot_id):
        row = next((row for row in self.list() if row['id'] == slot_id), None)
        if row is None:
            raise ValueError('房间槽位不存在，请刷新列表。')
        self.write(self.root/'slot-selection.json', {'format': 1, 'selected': slot_id})
        return row

    def create(self, name):
        name = self.validate_name(name)
        if any(row['name'].casefold() == name.casefold() for row in self.list()):
            raise ValueError('已有同名槽位，请使用不同名称。')
        slot_id = uuid.uuid4().hex
        path = self.path(slot_id)
        path.mkdir(parents=True)
        row = {'format': 1, 'id': slot_id, 'name': name,
               'createdAt': datetime.now().astimezone().isoformat(timespec='seconds')}
        self.write(path/'slot.json', row)
        self.select(slot_id)
        return row
