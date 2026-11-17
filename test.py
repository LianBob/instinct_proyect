
import os
import sys
import time

with open("personaje.txt", encoding="utf-8") as f:
    original = f.read().splitlines()

HEIGHT = len(original)
WIDTH = max(map(len, original))

original = [list(line.ljust(WIDTH)) for line in original]

# Inicio de la zona de las piernas
LEG_START = int(HEIGHT * 0.72)

# Cuatro posiciones de caminata
FRAMES = [
    (-2,  2),
    (-1,  1),
    ( 2, -2),
    ( 1, -1),
]

def make_frame(left_shift, right_shift):
    result = []

    for y, row in enumerate(original):
        new_row = [" "] * (WIDTH + 6)

        for x, char in enumerate(row):
            if char == " ":
                continue

            shift = 0

            if y >= LEG_START:
                center = WIDTH // 2

                if x < center:
                    shift = left_shift
                else:
                    shift = right_shift

            elif y >= LEG_START - 3:
                shift = (left_shift + right_shift) // 2

            new_x = x + shift + 3

            if 0 <= new_x < len(new_row):
                new_row[new_x] = char

        result.append("".join(new_row))

    return "\n".join(result)


frames = [make_frame(*position) for position in FRAMES]

# Animación
sys.stdout.write("\033[?25l")
sys.stdout.write("\033[2J")

try:
    while True:
        for frame in frames:
            sys.stdout.write("\033[H")
            sys.stdout.write(frame)
            sys.stdout.write("\033[J")
            sys.stdout.flush()

            time.sleep(0.14)

except KeyboardInterrupt:
    pass

finally:
    sys.stdout.write("\033[?25h\n")
    sys.stdout.flush()
