"""pygame match menu and replay viewer, with no game-rule implementation.

The menu starts ``arena.py`` in a separate process, then plays its JSON output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

WINDOW = (1280, 720)
SIDEBAR_WIDTH = 320
BACKGROUND = (8, 10, 16)
PANEL = (19, 23, 33)
PANEL_HOVER = (31, 38, 53)
GRID_LINE = (31, 36, 47)
TEXT = (235, 239, 247)
MUTED = (155, 164, 180)
ACCENT = (0, 220, 255)
WARNING = (255, 180, 70)


def load_replay(path: Path) -> dict[str, object]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    metadata, frames = replay["metadata"], replay["frames"]
    if not frames or int(metadata["width"]) < 1 or int(metadata["height"]) < 1:
        raise ValueError("replay has invalid metadata or no frames")
    return replay


def _brighten(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(min(255, channel + 65) for channel in color)


# Same-width ASCII stand-ins, so substituting one never shifts a padded column.
GLYPH_SUBSTITUTES = {"✓": "*", "•": "-", "←": "<", "→": ">", "↑": "^", "↓": "v", "—": "-", "×": "x"}


class SafeFont:
    """A font that replaces characters the face has no glyph for.

    pygame's bundled ``freesansbold.ttf`` has no check mark and no arrows, so
    those characters draw as empty "tofu" boxes.  Each character is compared
    against the face's rendering of an unassigned code point; the ones that come
    out identical are missing and get an ASCII stand-in instead.
    """

    def __init__(self, pygame, size: int) -> None:
        self.face = pygame.font.Font(None, size)
        undefined = pygame.image.tostring(self.face.render("\uffff", True, TEXT), "RGBA")
        self.substitutes = {
            character: replacement
            for character, replacement in GLYPH_SUBSTITUTES.items()
            if pygame.image.tostring(self.face.render(character, True, TEXT), "RGBA") == undefined
        }

    def render(self, text: str, antialias: bool, color: tuple[int, int, int]):
        for character, replacement in self.substitutes.items():
            text = text.replace(character, replacement)
        return self.face.render(text, antialias, color)


class MatchMenu:
    """Bot picker and subprocess coordinator; it knows no game rules."""

    def __init__(self, pygame, project: Path, bots_folder: Path, logs_folder: Path, fonts: dict[str, object]) -> None:
        self.pygame, self.project = pygame, project
        self.bots_folder, self.logs_folder, self.fonts = bots_folder, logs_folder, fonts
        self.catalog: list[dict[str, object]] = []
        self.selected: list[str] = []
        self.seed_text, self.seed_active, self.scroll = "42", False, 0
        self.status, self.running_match = "Loading bots...", False
        self.job: dict[str, object] = {}
        self.process: Optional[subprocess.Popen] = None
        self.refresh()

    def refresh(self) -> None:
        command = [sys.executable, str(self.project / "arena.py"), "--bots", str(self.bots_folder), "--list-bots"]
        try:
            completed = subprocess.run(command, cwd=self.project, stdout=subprocess.PIPE, text=True, timeout=10, check=False)
            if completed.returncode:
                raise RuntimeError(f"bot scan exited with code {completed.returncode}")
            catalog = json.loads(completed.stdout)
            if not isinstance(catalog, list):
                raise ValueError("unexpected bot catalog")
            self.catalog = catalog
            available = {str(item["source"]) for item in catalog}
            self.selected = [source for source in self.selected if source in available]
            self.scroll = min(self.scroll, max(0, (len(catalog) + 1) // 2 - 7))
            self.status = f"Found {len(catalog)} valid bots. Select 2 to 4."
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            self.catalog, self.selected = [], []
            self.status = f"Could not load bots: {exc}"

    def _visible_rows(self) -> list[tuple[object, dict[str, object]]]:
        rows = []
        for index, item in enumerate(self.catalog[self.scroll * 2 : self.scroll * 2 + 14]):
            rect = self.pygame.Rect(120 + index % 2 * 520, 148 + index // 2 * 52, 490, 42)
            rows.append((rect, item))
        return rows

    def _begin_match(self) -> None:
        if self.running_match:
            return
        if not 2 <= len(self.selected) <= 4:
            self.status = "Choose at least 2 and no more than 4 bots."
            return
        try:
            seed = int(self.seed_text)
        except ValueError:
            self.status = "Seed must be a whole number."
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = self.logs_folder / f"practice_{timestamp}_seed_{seed}.json"
        command = [sys.executable, str(self.project / "arena.py"), "--bot-files", *self.selected, "--seed", str(seed), "--out", str(output)]
        self.running_match, self.status, self.job = True, "Running bots headlessly...", {}

        def worker() -> None:
            try:
                self.process = subprocess.Popen(command, cwd=self.project)
                returncode = self.process.wait()
                if returncode == 0:
                    self.job["path"] = output
                else:
                    self.job["error"] = f"Arena exited with code {returncode}. See the console."
            except OSError as exc:
                self.job["error"] = f"Could not start arena: {exc}"
            self.process = None
            self.job["done"] = True

        threading.Thread(target=worker, daemon=True).start()

    def consume_finished_match(self) -> Optional[Path]:
        if not self.running_match or not self.job.get("done"):
            return None
        self.running_match = False
        if "error" in self.job:
            self.status = str(self.job["error"])
            return None
        self.status = "Replay ready."
        return Path(self.job["path"])

    def handle_event(self, event) -> str:
        pygame = self.pygame
        if event.type == pygame.QUIT:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            return "quit"
        if event.type == pygame.MOUSEWHEEL:
            maximum = max(0, (len(self.catalog) + 1) // 2 - 7)
            self.scroll = max(0, min(maximum, self.scroll - event.y))
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, item in self._visible_rows():
                if rect.collidepoint(event.pos) and not self.running_match:
                    source = str(item["source"])
                    if source in self.selected:
                        self.selected.remove(source)
                    elif len(self.selected) < 4:
                        self.selected.append(source)
                    else:
                        self.status = "A match can have at most 4 bots."
                    return ""
            self.seed_active = pygame.Rect(360, 548, 170, 44).collidepoint(event.pos)
            if pygame.Rect(846, 548, 190, 44).collidepoint(event.pos):
                self._begin_match()
            elif pygame.Rect(1050, 548, 110, 44).collidepoint(event.pos) and not self.running_match:
                self.refresh()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                return "fullscreen"
            if event.key == pygame.K_ESCAPE:
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                return "quit"
            if event.key == pygame.K_RETURN and not self.seed_active:
                self._begin_match()
            elif self.seed_active:
                if event.key == pygame.K_RETURN:
                    self.seed_active = False
                    self._begin_match()
                elif event.key == pygame.K_BACKSPACE:
                    self.seed_text = self.seed_text[:-1]
                elif event.unicode.isdigit() or (event.unicode == "-" and not self.seed_text):
                    if len(self.seed_text) < 12:
                        self.seed_text += event.unicode
        return ""

    def draw(self, screen) -> None:
        pygame = self.pygame
        font, small, title = self.fonts["font"], self.fonts["small"], self.fonts["title"]
        screen.fill(BACKGROUND)
        screen.blit(title.render("TRON BOT ARENA", True, TEXT), (120, 42))
        screen.blit(font.render("Practice match setup", True, ACCENT), (120, 93))
        screen.blit(small.render("Choose competitors. Bots run headlessly first, then the replay starts automatically.", True, MUTED), (403, 100))
        mouse = pygame.mouse.get_pos()
        for rect, item in self._visible_rows():
            source, chosen = str(item["source"]), str(item["source"]) in self.selected
            pygame.draw.rect(screen, PANEL_HOVER if rect.collidepoint(mouse) else PANEL, rect, border_radius=7)
            pygame.draw.rect(screen, tuple(item["color"]) if chosen else GRID_LINE, rect, 3 if chosen else 1, border_radius=7)
            screen.blit(font.render(("✓ " if chosen else "  ") + str(item["name"]), True, TEXT), (rect.x + 13, rect.y + 8))
        pygame.draw.rect(screen, PANEL, (120, 528, 1040, 84), border_radius=9)
        screen.blit(font.render(f"Selected: {len(self.selected)} / 4", True, TEXT), (142, 557))
        screen.blit(small.render("Seed", True, MUTED), (360, 531))
        seed_rect = pygame.Rect(360, 548, 170, 44)
        pygame.draw.rect(screen, BACKGROUND, seed_rect, border_radius=5)
        pygame.draw.rect(screen, ACCENT if self.seed_active else GRID_LINE, seed_rect, 2, border_radius=5)
        screen.blit(font.render(self.seed_text or " ", True, TEXT), (seed_rect.x + 12, seed_rect.y + 9))
        run_rect = pygame.Rect(846, 548, 190, 44)
        run_enabled = 2 <= len(self.selected) <= 4 and not self.running_match
        pygame.draw.rect(screen, ACCENT if run_enabled else GRID_LINE, run_rect, border_radius=6)
        run_text = font.render("RUNNING..." if self.running_match else "RUN MATCH", True, BACKGROUND if run_enabled else MUTED)
        screen.blit(run_text, run_text.get_rect(center=run_rect.center))
        refresh_rect = pygame.Rect(1050, 548, 110, 44)
        pygame.draw.rect(screen, PANEL_HOVER, refresh_rect, border_radius=6)
        refresh_text = small.render("REFRESH", True, TEXT)
        screen.blit(refresh_text, refresh_text.get_rect(center=refresh_rect.center))
        status_color = WARNING if self.status.startswith(("Could", "Choose", "Seed", "Arena")) else MUTED
        screen.blit(small.render(self.status, True, status_color), (120, 636))
        screen.blit(small.render(f"Bot folder: {self.bots_folder}", True, MUTED), (120, 665))
        screen.blit(small.render("Mouse wheel scrolls • F11 fullscreen • Esc quits", True, MUTED), (836, 665))


class ReplayPlayer:
    def __init__(self, pygame, replay: dict[str, object], fonts: dict[str, object]) -> None:
        self.pygame, self.replay, self.fonts = pygame, replay, fonts
        self.metadata, self.frames = replay["metadata"], replay["frames"]
        self.width, self.height = int(self.metadata["width"]), int(self.metadata["height"])
        self.arena_width = WINDOW[0] - SIDEBAR_WIDTH
        self.cell = max(1, min(self.arena_width // self.width, WINDOW[1] // self.height))
        self.board_width, self.board_height = self.width * self.cell, self.height * self.cell
        self.board_x = (self.arena_width - self.board_width) // 2
        self.board_y = (WINDOW[1] - self.board_height) // 2
        self.bot_meta = {str(bot["id"]): bot for bot in self.metadata["bots"]}
        self.colors = {bot_id: tuple(item["color"]) for bot_id, item in self.bot_meta.items()}
        self.owner_grid: list[list[Optional[str]]] = []
        self.frame_index, self.paused, self.speed, self.accumulator = 0, False, 8.0, 0.0
        self.rebuild_grid(0)

    def rebuild_grid(self, target: int) -> None:
        self.owner_grid = [[None] * self.width for _ in range(self.height)]
        for frame in self.frames[: target + 1]:
            for update in frame.get("trail_updates", []):
                self.owner_grid[int(update["y"])][int(update["x"])] = str(update["bot_id"])

    def handle_event(self, event) -> str:
        pygame = self.pygame
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                return "fullscreen"
            if event.key == pygame.K_m:
                return "menu"
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key == pygame.K_r:
                self.frame_index, self.accumulator, self.paused = 0, 0.0, False
                self.rebuild_grid(0)
            elif event.key == pygame.K_UP:
                self.speed = min(64.0, self.speed * 2)
            elif event.key == pygame.K_DOWN:
                self.speed = max(0.5, self.speed / 2)
            elif event.key == pygame.K_RIGHT and self.paused:
                self.frame_index = min(len(self.frames) - 1, self.frame_index + 1)
                self.rebuild_grid(self.frame_index)
            elif event.key == pygame.K_LEFT and self.paused:
                self.frame_index = max(0, self.frame_index - 1)
                self.rebuild_grid(self.frame_index)
        return ""

    def update(self, elapsed: float) -> None:
        if self.paused or self.frame_index >= len(self.frames) - 1:
            return
        self.accumulator += elapsed * self.speed
        while self.accumulator >= 1.0 and self.frame_index < len(self.frames) - 1:
            self.frame_index += 1
            for update in self.frames[self.frame_index].get("trail_updates", []):
                self.owner_grid[int(update["y"])][int(update["x"])] = str(update["bot_id"])
            self.accumulator -= 1.0

    def draw(self, screen) -> None:
        pygame = self.pygame
        font, small, banner = self.fonts["font"], self.fonts["small"], self.fonts["banner"]
        screen.fill(BACKGROUND)
        for y, row in enumerate(self.owner_grid):
            for x, owner in enumerate(row):
                if owner is not None:
                    pygame.draw.rect(screen, self.colors[owner], (self.board_x + x * self.cell + 2, self.board_y + y * self.cell + 2, max(1, self.cell - 3), max(1, self.cell - 3)))
        for x in range(self.width + 1):
            pygame.draw.line(screen, GRID_LINE, (self.board_x + x * self.cell, self.board_y), (self.board_x + x * self.cell, self.board_y + self.board_height))
        for y in range(self.height + 1):
            pygame.draw.line(screen, GRID_LINE, (self.board_x, self.board_y + y * self.cell), (self.board_x + self.board_width, self.board_y + y * self.cell))
        current = self.frames[self.frame_index]
        for bot in current["bots"]:
            color = self.colors[str(bot["id"])]
            center = (self.board_x + int(bot["x"]) * self.cell + self.cell // 2, self.board_y + int(bot["y"]) * self.cell + self.cell // 2)
            pygame.draw.circle(screen, _brighten(color), center, max(4, self.cell // 2 - 1))
            if not bot["alive"]:
                pygame.draw.line(screen, BACKGROUND, (center[0] - 5, center[1] - 5), (center[0] + 5, center[1] + 5), 3)
                pygame.draw.line(screen, BACKGROUND, (center[0] + 5, center[1] - 5), (center[0] - 5, center[1] + 5), 3)
        panel_x = self.arena_width + 24
        screen.blit(font.render("TRON BOT ARENA", True, TEXT), (panel_x, 24))
        screen.blit(small.render(f"Tick {current['tick']} / {self.frames[-1]['tick']}", True, TEXT), (panel_x, 62))
        screen.blit(small.render(f"Speed {self.speed:g} ticks/s" + ("  PAUSED" if self.paused else ""), True, MUTED), (panel_x, 86))
        y_pos = 132
        for bot in current["bots"]:
            item, color = self.bot_meta[str(bot["id"])], self.colors[str(bot["id"])]
            pygame.draw.rect(screen, color, (panel_x, y_pos + 3, 16, 16))
            status = "ALIVE" if bot["alive"] else "DEAD"
            screen.blit(font.render(str(item["name"]), True, TEXT), (panel_x + 26, y_pos))
            screen.blit(small.render(f"{status}  trail: {bot['trail_length']}", True, color if bot["alive"] else MUTED), (panel_x + 26, y_pos + 27))
            y_pos += 68
        controls = ["F11     fullscreen toggle", "SPACE  pause / resume", "← →    step while paused", "↑ ↓     change speed", "R       restart", "M       match menu", "ESC     quit"]
        for number, line in enumerate(controls):
            screen.blit(small.render(line, True, MUTED), (panel_x, 420 + number * 25))
        if current.get("errors"):
            screen.blit(small.render(f"Bot errors this tick: {len(current['errors'])}", True, WARNING), (panel_x, 608))
        if self.frame_index == len(self.frames) - 1:
            winners = [p["name"] for p in self.replay["results"]["placements"] if p["place"] == 1]
            label = "DRAW: " + " & ".join(winners) if len(winners) > 1 else "WINNER: " + winners[0]
            surface = banner.render(label, True, TEXT)
            box, backdrop = surface.get_rect(center=(self.arena_width // 2, 54)), surface.get_rect(center=(self.arena_width // 2, 54)).inflate(32, 18)
            pygame.draw.rect(screen, PANEL, backdrop, border_radius=8)
            pygame.draw.rect(screen, (255, 220, 80), backdrop, width=2, border_radius=8)
            screen.blit(surface, box)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Set up Tron matches or play a JSON replay.")
    parser.add_argument("replay", type=Path, nargs="?", help="optional replay to open immediately")
    parser.add_argument("--bots", type=Path, default=Path("bots"), help="bot folder shown in the match menu")
    parser.add_argument("--logs", type=Path, default=Path("logs"), help="where menu-generated practice logs are saved")
    args = parser.parse_args(argv)
    initial_replay = None
    if args.replay:
        try:
            initial_replay = load_replay(args.replay)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            parser.error(f"cannot load replay: {exc}")
    try:
        import pygame
    except ImportError:
        parser.error("pygame is not installed; run: python -m pip install -r requirements.txt")
    pygame.init()
    screen = pygame.display.set_mode(WINDOW)
    pygame.display.set_caption("Tron Bot Arena")
    clock = pygame.time.Clock()
    fonts = {"small": SafeFont(pygame, 22), "font": SafeFont(pygame, 28), "title": SafeFont(pygame, 52), "banner": SafeFont(pygame, 54)}
    project = Path(__file__).resolve().parent
    menu = MatchMenu(pygame, project, args.bots.resolve(), args.logs.resolve(), fonts)
    player = ReplayPlayer(pygame, initial_replay, fonts) if initial_replay else None
    mode = "player" if player else "menu"
    running = True
    while running:
        elapsed = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            action = menu.handle_event(event) if mode == "menu" else player.handle_event(event)
            if action == "quit":
                running = False
            elif action == "fullscreen":
                # F11 is intentionally opt-in: the default remains a predictable
                # 1280x720 window, while pygame negotiates the projector mode here.
                # On some SDL/macOS builds this returns a status integer rather
                # than a Surface, while the display surface is recreated in place.
                pygame.display.toggle_fullscreen()
                screen = pygame.display.get_surface()
            elif action == "menu":
                mode = "menu"
                pygame.display.set_caption("Tron Bot Arena — Match Setup")
        if mode == "menu":
            replay_path = menu.consume_finished_match()
            if replay_path:
                try:
                    player = ReplayPlayer(pygame, load_replay(replay_path), fonts)
                    mode = "player"
                    pygame.display.set_caption(f"Tron Bot Arena — {replay_path.name}")
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    menu.status = f"Could not open generated replay: {exc}"
            menu.draw(screen)
        else:
            player.update(elapsed)
            player.draw(screen)
        pygame.display.flip()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
