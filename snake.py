#!/usr/bin/env python3
"""Змейка для терминала.

Управление:
    стрелки или WASD — движение
    P               — пауза
    Q               — выход

Запуск:
    python3 snake.py

Использует только стандартную библиотеку (модуль curses),
поэтому ничего доустанавливать не нужно (Linux/macOS).
"""

import curses
import random
from collections import deque

# Направления как (dy, dx).
UP = (-1, 0)
DOWN = (1, 0)
LEFT = (0, -1)
RIGHT = (0, 1)

# Клавиша -> направление.
KEY_TO_DIR = {
    curses.KEY_UP: UP,
    curses.KEY_DOWN: DOWN,
    curses.KEY_LEFT: LEFT,
    curses.KEY_RIGHT: RIGHT,
    ord("w"): UP,
    ord("s"): DOWN,
    ord("a"): LEFT,
    ord("d"): RIGHT,
    ord("W"): UP,
    ord("S"): DOWN,
    ord("A"): LEFT,
    ord("D"): RIGHT,
}

# Скорость: задержка кадра в миллисекундах. Меньше — быстрее.
START_DELAY = 120
MIN_DELAY = 55
SPEEDUP_EVERY = 4  # каждые N съеденных ускоряемся


class SnakeGame:
    def __init__(self, screen):
        self.screen = screen
        self.height, self.width = screen.getmaxyx()
        # Игровое поле — вся область минус рамка.
        self.top, self.left = 1, 1
        self.bottom, self.right = self.height - 2, self.width - 2

        self.reset()

    def reset(self):
        cy = (self.top + self.bottom) // 2
        cx = (self.left + self.right) // 2
        # Голова спереди (индекс 0), хвост в конце.
        self.snake = deque([(cy, cx), (cy, cx - 1), (cy, cx - 2)])
        self.occupied = set(self.snake)
        self.direction = RIGHT
        self.pending_dir = RIGHT
        self.score = 0
        self.delay = START_DELAY
        self.paused = False
        self.food = self._place_food()

    def _place_food(self):
        free = [
            (y, x)
            for y in range(self.top, self.bottom + 1)
            for x in range(self.left, self.right + 1)
            if (y, x) not in self.occupied
        ]
        if not free:
            return None  # поле заполнено — победа
        return random.choice(free)

    def _opposite(self, a, b):
        return a[0] == -b[0] and a[1] == -b[1]

    def handle_input(self, key):
        if key in (ord("q"), ord("Q")):
            return "quit"
        if key in (ord("p"), ord("P")):
            self.paused = not self.paused
            return None
        if key in KEY_TO_DIR:
            new_dir = KEY_TO_DIR[key]
            # Нельзя развернуться на 180 градусов.
            if not self._opposite(new_dir, self.direction):
                self.pending_dir = new_dir
        return None

    def step(self):
        """Один игровой тик. Возвращает 'dead', 'win' или None."""
        if self.paused:
            return None

        self.direction = self.pending_dir
        head_y, head_x = self.snake[0]
        dy, dx = self.direction
        new_head = (head_y + dy, head_x + dx)
        ny, nx = new_head

        # Столкновение со стеной.
        if not (self.top <= ny <= self.bottom and self.left <= nx <= self.right):
            return "dead"

        ate = new_head == self.food

        # Хвост уедет вперёд, если мы не едим — значит на его клетку можно.
        tail = self.snake[-1]
        body_to_check = self.occupied - ({tail} if not ate else set())
        if new_head in body_to_check:
            return "dead"

        # Двигаем змейку.
        self.snake.appendleft(new_head)
        self.occupied.add(new_head)
        if ate:
            self.score += 1
            if self.score % SPEEDUP_EVERY == 0:
                self.delay = max(MIN_DELAY, self.delay - 8)
            self.food = self._place_food()
            if self.food is None:
                return "win"
        else:
            removed = self.snake.pop()
            self.occupied.discard(removed)

        return None

    def draw(self):
        s = self.screen
        s.erase()
        s.border()

        title = " ЗМЕЙКА "
        s.addstr(0, max(2, (self.width - len(title)) // 2), title, curses.A_BOLD)

        status = f" Счёт: {self.score}   P — пауза   Q — выход "
        if len(status) < self.width - 2:
            s.addstr(self.height - 1, 2, status)

        # Еда.
        if self.food:
            fy, fx = self.food
            s.addstr(fy, fx, "@", curses.color_pair(2) | curses.A_BOLD)

        # Змейка: голова отдельным символом.
        for i, (y, x) in enumerate(self.snake):
            ch = "O" if i == 0 else "o"
            s.addstr(y, x, ch, curses.color_pair(1) | curses.A_BOLD)

        if self.paused:
            msg = " ПАУЗА — нажми P "
            s.addstr(self.height // 2, (self.width - len(msg)) // 2, msg,
                     curses.A_REVERSE)

        s.refresh()


def center_msg(screen, lines):
    h, w = screen.getmaxyx()
    start = h // 2 - len(lines) // 2
    for i, line in enumerate(lines):
        screen.addstr(start + i, max(0, (w - len(line)) // 2), line, curses.A_BOLD)
    screen.refresh()


def game_over_screen(screen, score, won):
    screen.nodelay(False)
    header = "ПОБЕДА! Поле заполнено!" if won else "GAME OVER"
    lines = [
        header,
        "",
        f"Твой счёт: {score}",
        "",
        "Enter — сыграть ещё раз",
        "Q — выход",
    ]
    screen.erase()
    screen.border()
    center_msg(screen, lines)
    while True:
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return False
        if key in (curses.KEY_ENTER, 10, 13):
            return True


def run(screen):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # змейка
    curses.init_pair(2, curses.COLOR_RED, -1)     # еда

    if screen.getmaxyx()[0] < 10 or screen.getmaxyx()[1] < 30:
        screen.nodelay(False)
        center_msg(screen, ["Слишком маленькое окно.",
                            "Увеличь терминал и запусти снова."])
        screen.getch()
        return

    while True:
        game = SnakeGame(screen)
        screen.nodelay(True)

        result = None
        while result is None:
            screen.timeout(game.delay)
            key = screen.getch()
            if key != -1:
                if game.handle_input(key) == "quit":
                    return
            result = game.step()
            game.draw()

        if not game_over_screen(screen, game.score, result == "win"):
            return


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
