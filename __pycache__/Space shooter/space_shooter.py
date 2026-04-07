import math
import random
import tkinter as tk


SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
FRAME_MS = int(1000 / FPS)


BLACK = "#000000"
GREEN = "#00ff00"
DARK_GREEN = "#006400"
LIGHT_GREEN = "#32ff32"
BRIGHT_GREEN = "#96ff96"


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def aabb_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


class Star:
    def __init__(self) -> None:
        self.x = random.uniform(0, SCREEN_WIDTH)
        self.y = random.uniform(0, SCREEN_HEIGHT)
        self.speed = random.uniform(0.6, 2.2)
        self.size = random.choice((1, 1, 2, 2, 3))

    def update(self) -> None:
        self.y += self.speed
        if self.y > SCREEN_HEIGHT + 3:
            self.y = -3
            self.x = random.uniform(0, SCREEN_WIDTH)

    def draw(self, canvas: tk.Canvas) -> None:
        r = self.size
        color = GREEN if r == 1 else LIGHT_GREEN if r == 2 else BRIGHT_GREEN
        canvas.create_oval(self.x - r, self.y - r, self.x + r, self.y + r, fill=color, outline="")


class Bullet:
    def __init__(self, x: float, y: float, vy: float, friendly: bool) -> None:
        self.x = x
        self.y = y
        self.vy = vy
        self.friendly = friendly
        self.w = 3
        self.h = 10

    def update(self) -> None:
        self.y += self.vy

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - self.w / 2, self.y, self.x + self.w / 2, self.y + self.h)

    def draw(self, canvas: tk.Canvas) -> None:
        color = LIGHT_GREEN if self.friendly else BRIGHT_GREEN
        x1, y1, x2, y2 = self.bbox()
        canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")


class Player:
    def __init__(self) -> None:
        self.w = 34
        self.h = 34
        self.x = SCREEN_WIDTH / 2
        self.y = SCREEN_HEIGHT - 70
        self.speed = 5.5
        self.bullets: list[Bullet] = []
        self.cooldown = 0

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - self.w / 2, self.y - self.h / 2, self.x + self.w / 2, self.y + self.h / 2)

    def update(self, keys: set[str]) -> None:
        dx = 0.0
        dy = 0.0
        if "Left" in keys:
            dx -= self.speed
        if "Right" in keys:
            dx += self.speed
        if "Up" in keys:
            dy -= self.speed
        if "Down" in keys:
            dy += self.speed

        self.x = clamp(self.x + dx, self.w / 2, SCREEN_WIDTH - self.w / 2)
        self.y = clamp(self.y + dy, self.h / 2, SCREEN_HEIGHT - self.h / 2)

        if self.cooldown > 0:
            self.cooldown -= 1

        for b in self.bullets[:]:
            b.update()
            if b.y + b.h < 0:
                self.bullets.remove(b)

    def shoot(self) -> None:
        if self.cooldown <= 0:
            self.bullets.append(Bullet(self.x, self.y - self.h / 2 - 10, vy=-10, friendly=True))
            self.cooldown = 10

    def draw(self, canvas: tk.Canvas) -> None:
        x = self.x
        y = self.y
        points = [
            x, y - self.h / 2,
            x - self.w / 2, y + self.h / 2,
            x + self.w / 2, y + self.h / 2,
        ]
        canvas.create_polygon(points, fill=GREEN, outline=LIGHT_GREEN, width=2)
        for b in self.bullets:
            b.draw(canvas)


class Enemy:
    def __init__(self, x: float, y: float, wave: int) -> None:
        self.w = 28
        self.h = 28
        self.x = x
        self.y = y
        self.base_x = x
        self.phase = random.uniform(0, math.tau)
        self.speed = random.uniform(1.3, 2.8) + min(1.2, wave * 0.08)
        self.bullets: list[Bullet] = []
        self.shoot_timer = random.randint(50, 120)
        self.wave = wave

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x - self.w / 2, self.y - self.h / 2, self.x + self.w / 2, self.y + self.h / 2)

    def update(self) -> None:
        self.y += self.speed
        self.x = self.base_x + math.sin((self.y * 0.03) + self.phase) * (18 + min(30, self.wave * 2))
        self.x = clamp(self.x, self.w / 2, SCREEN_WIDTH - self.w / 2)

        if self.shoot_timer > 0:
            self.shoot_timer -= 1
        else:
            self.bullets.append(Bullet(self.x, self.y + self.h / 2 + 2, vy=6.5, friendly=False))
            self.shoot_timer = random.randint(75, 160)

        for b in self.bullets[:]:
            b.update()
            if b.y > SCREEN_HEIGHT + 30:
                self.bullets.remove(b)

    def draw(self, canvas: tk.Canvas) -> None:
        x = self.x
        y = self.y
        points = [
            x, y + self.h / 2,
            x - self.w / 2, y - self.h / 2,
            x + self.w / 2, y - self.h / 2,
        ]
        canvas.create_polygon(points, fill=DARK_GREEN, outline=GREEN, width=2)
        for b in self.bullets:
            b.draw(canvas)


class Game:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Retro Space Shooter (Tk)")
        self.root.configure(bg=BLACK)
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(self.root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, bg=BLACK, highlightthickness=0)
        self.canvas.pack()

        self.keys_down: set[str] = set()
        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)

        self._running = True

        self.reset_game()
        self.tick()

    def reset_game(self) -> None:
        self.player = Player()
        self.enemies: list[Enemy] = []
        self.stars = [Star() for _ in range(55)]
        self.score = 0
        self.wave = 1
        self.game_over = False
        self.spawn_timer = 0
        self.flash_timer = 0

    def on_key_down(self, event: tk.Event) -> None:
        if event.keysym == "Escape":
            self._running = False
            self.root.destroy()
            return

        if event.keysym == "r" and self.game_over:
            self.reset_game()
            return

        self.keys_down.add(str(event.keysym))

    def on_key_up(self, event: tk.Event) -> None:
        self.keys_down.discard(str(event.keysym))

    def spawn_enemy(self) -> None:
        if self.spawn_timer > 0:
            self.spawn_timer -= 1
            return

        x = random.uniform(40, SCREEN_WIDTH - 40)
        self.enemies.append(Enemy(x=x, y=-40, wave=self.wave))
        base = max(18, 65 - self.wave * 4)
        self.spawn_timer = random.randint(base, base + 25)

    def update(self) -> None:
        if self.flash_timer > 0:
            self.flash_timer -= 1

        for s in self.stars:
            s.update()

        if self.game_over:
            return

        self.player.update(self.keys_down)
        if "space" in self.keys_down or "Space" in self.keys_down:
            self.player.shoot()

        self.spawn_enemy()

        for e in self.enemies[:]:
            e.update()
            if e.y - e.h / 2 > SCREEN_HEIGHT + 60:
                self.enemies.remove(e)

        # Collisions: player bullets vs enemies
        for b in self.player.bullets[:]:
            bb = b.bbox()
            hit = None
            for e in self.enemies:
                if aabb_intersect(bb, e.bbox()):
                    hit = e
                    break
            if hit is not None:
                if b in self.player.bullets:
                    self.player.bullets.remove(b)
                if hit in self.enemies:
                    self.enemies.remove(hit)
                self.score += 10
                self.flash_timer = 3

        # Collisions: enemy bullets vs player
        pbox = self.player.bbox()
        for e in self.enemies:
            for b in e.bullets[:]:
                if aabb_intersect(b.bbox(), pbox):
                    self.game_over = True
                    return

        # Collisions: enemy ship vs player
        for e in self.enemies:
            if aabb_intersect(e.bbox(), pbox):
                self.game_over = True
                return

        self.wave = (self.score // 100) + 1

    def draw_scanlines(self) -> None:
        # Light scanline effect
        for y in range(0, SCREEN_HEIGHT, 4):
            self.canvas.create_line(0, y, SCREEN_WIDTH, y, fill="#001a00")

    def draw(self) -> None:
        bg = "#001000" if self.flash_timer > 0 else BLACK
        self.canvas.delete("all")
        self.canvas.configure(bg=bg)

        for s in self.stars:
            s.draw(self.canvas)

        for e in self.enemies:
            e.draw(self.canvas)

        self.player.draw(self.canvas)

        self.draw_scanlines()

        self.canvas.create_text(10, 10, anchor="nw", text=f"SCORE: {self.score}", fill=GREEN, font=("Consolas", 18, "bold"))
        self.canvas.create_text(10, 34, anchor="nw", text=f"WAVE: {self.wave}", fill=LIGHT_GREEN, font=("Consolas", 12, "bold"))

        if self.game_over:
            self.canvas.create_text(
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2,
                text="GAME OVER",
                fill=GREEN,
                font=("Consolas", 32, "bold"),
            )
            self.canvas.create_text(
                SCREEN_WIDTH / 2,
                SCREEN_HEIGHT / 2 + 44,
                text="Press R to Restart   |   ESC to Quit",
                fill=LIGHT_GREEN,
                font=("Consolas", 14, "bold"),
            )

    def tick(self) -> None:
        if not self._running:
            return
        self.update()
        self.draw()
        self.root.after(FRAME_MS, self.tick)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Game().run()

