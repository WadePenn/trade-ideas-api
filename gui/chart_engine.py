import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image, ImageTk

class ChartEngine:
    def __init__(self):
        pass

    def render_line(self, parent, data):
        fig, ax = plt.subplots(figsize=(5, 2))
        ax.plot(data, color="#3a8cff")
        ax.set_facecolor("#1e1e1e")
        fig.patch.set_facecolor("#1e1e1e")
        ax.tick_params(colors="white")

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)

        img = Image.open(buf)
        tk_img = ImageTk.PhotoImage(img)

        label = tk.Label(parent, image=tk_img, bg="#1e1e1e")
        label.image = tk_img
        label.pack()

chart_engine = ChartEngine()
