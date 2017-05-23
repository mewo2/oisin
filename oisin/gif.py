import PIL
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw


def render_poem(poem, w=10):
    lines = poem.split('\n')
    h = 21 * len(lines) + 26
    font = ImageFont.truetype("Courier New Bold.ttf", 20)
    img = Image.new("RGBA", (12 * (w + 2), h), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((12, 12), poem, (255, 255, 255), font=font)
    return img


def animate(poems, filename, pause=100):
    maxw = max(max(len(l) for l in poem.split('\n')) for poem in poems)
    imgs = [render_poem(poem, maxw) for poem in poems]
    imgs[0].save(
        filename,
        save_all=True,
        append_images=imgs[1:] + [imgs[-1].copy() for _ in range(pause)],
        loop=0,
        duration=500)
