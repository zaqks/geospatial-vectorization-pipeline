from PIL import Image

img = Image.open("../data/el_harrach_highres_map.png")
img = img.resize((img.width // 4, img.height // 4))

img.save(
    "../data/el_harrach_highres_map_compressed.png",
    format="PNG",
    optimize=True,
    # compress_level=9
)