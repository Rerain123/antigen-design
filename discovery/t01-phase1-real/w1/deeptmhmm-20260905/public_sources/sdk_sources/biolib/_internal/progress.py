import re
import shutil
import sys
import time
from typing import Dict, List, Optional

_MARKUP_PATTERN = re.compile(r'\[/?[a-zA-Z][a-zA-Z ]*\]')


def _strip_markup(text: str) -> str:
    return _MARKUP_PATTERN.sub('', text)


def _format_size(num_bytes: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(num_bytes) < 1024:
            return f'{num_bytes:.1f} {unit}'
        num_bytes /= 1024
    return f'{num_bytes:.1f} PB'


def _format_time_remaining(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


class _Task:
    def __init__(self, description: str, total: float):
        self.description = description
        self.total = total
        self.completed = 0.0
        self.start_time = time.monotonic()


class Progress:
    def __init__(self, show_speed: bool = False) -> None:
        self._tasks: Dict[int, _Task] = {}
        self._task_order: List[int] = []
        self._next_id = 0
        self._show_speed = show_speed
        self._lines_rendered = 0

    def __enter__(self) -> 'Progress':
        return self

    def __exit__(self, *args: object) -> None:
        if self._lines_rendered > 0:
            sys.stderr.write('\n')
            sys.stderr.flush()

    def add_task(self, description: str = '', total: Optional[float] = None) -> int:
        task_id = self._next_id
        self._next_id += 1
        self._tasks[task_id] = _Task(_strip_markup(description), total or 0.0)
        self._task_order.append(task_id)
        self._render()
        return task_id

    def update(
        self,
        task_id: int,
        *,
        completed: Optional[float] = None,
        total: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        if completed is not None:
            task.completed = completed
        if total is not None:
            task.total = total
        if description is not None:
            task.description = _strip_markup(description)
        self._render()

    def _render(self) -> None:
        cols = shutil.get_terminal_size((80, 24)).columns
        if self._lines_rendered > 0:
            move_up_line_count = self._lines_rendered - 1
            if move_up_line_count > 0:
                sys.stderr.write(f'\x1b[{move_up_line_count}A')
            sys.stderr.write('\r\x1b[J')
        lines = [self._format_task(self._tasks[tid], cols) for tid in self._task_order]
        sys.stderr.write('\n'.join(lines))
        sys.stderr.flush()
        self._lines_rendered = len(lines)

    def _format_task(self, task: _Task, width: int) -> str:
        desc = task.description
        fraction = min(task.completed / task.total, 1.0) if task.total > 0 else 0.0
        suffix = f'{fraction * 100:5.1f}%' if task.total > 0 else ''

        if self._show_speed and task.total > 0:
            elapsed = time.monotonic() - task.start_time
            speed = task.completed / elapsed if elapsed > 0 else 0.0
            suffix += f'  {_format_size(speed)}/s'
            if 0 < fraction < 1.0 and elapsed > 0:
                remaining = (elapsed / fraction) * (1.0 - fraction)
                suffix += f'  {_format_time_remaining(remaining)}'

        if task.total <= 0:
            return f'{desc}  {suffix}'[:width]

        bar_width = max(width - len(desc) - len(suffix) - 4, 10)
        filled = int(bar_width * fraction)
        progress_bar = '\u2501' * filled + '\u2500' * (bar_width - filled)
        return f'{desc}  {progress_bar}  {suffix}'[:width]
