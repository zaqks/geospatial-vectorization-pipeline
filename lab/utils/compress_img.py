from PIL import Image

img = Image.open("../data/el_harrach_highres_map.png")
img = img.resize((img.width // 2, img.height // 2))

img.save(
    "../data/el_harrach_highres_map.png",
    format="PNG",
    optimize=True,
    compress_level=9
)