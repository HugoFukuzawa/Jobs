from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np
import os
import re
from tkinter import Tk, filedialog, messagebox

header_h, footer_h, fade_f, duration, resize_dim = 50, 50, 20, 2, (800, 800)
font_p = "arial.ttf"

def get_date(filename):
    cleaned = filename.replace('combined_openEO_', '')
    match = re.search(r'\d{4}-\d{2}-\d{2}', cleaned)
    return match.group(0) if match else "Data Desconhecida"

def fade_imgs(img1, img2, steps=fade_f):
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
    return [Image.blend(img1, img2, i / float(steps)) for i in range(steps + 1)]

def main():
    root = Tk()
    root.withdraw()
    in_folder = filedialog.askdirectory(title="Selecione a pasta com as imagens PNG combinadas")
    if not in_folder:
        messagebox.showerror("Erro", "Pasta de entrada não selecionada.")
        root.destroy()
        return
    out_folder = filedialog.askdirectory(title="Selecione a pasta para salvar o GIF")
    if not out_folder:
        messagebox.showerror("Erro", "Pasta de saída não selecionada.")
        root.destroy()
        return
    print("Iniciando processamento...")
    out_gif = os.path.join(out_folder, "biomassa_analysis.gif")
    img_paths = [os.path.join(in_folder, f) for f in sorted(os.listdir(in_folder)) if f.endswith('.png')]
    if not img_paths:
        messagebox.showerror("Erro", "Nenhuma imagem PNG encontrada.")
        root.destroy()
        return
    try:
        font, title_font = ImageFont.truetype(font_p, 20), ImageFont.truetype(font_p, 24)
    except IOError:
        font = title_font = ImageFont.load_default()
    title_txt = "Análise de Biomassa - Centro de Tecnologia Canavieira (CTC)"
    title_img = Image.new("RGB", (resize_dim[0], header_h), "black")
    draw_title = ImageDraw.Draw(title_img)
    title_bbox = draw_title.textbbox((0, 0), title_txt, font=title_font)
    x_title, y_title = (title_img.width - title_bbox[2]) // 2, (header_h - title_bbox[3]) // 2
    draw_title.text((x_title, y_title), title_txt, font=title_font, fill="white")
    with imageio.get_writer(out_gif, mode='I', duration=duration) as writer:
        prev_img = None
        for path in img_paths:
            img = Image.open(path)
            if img.size != resize_dim:
                img.thumbnail(resize_dim, Image.Resampling.LANCZOS)
            img_with_hf = Image.new("RGB", (img.width, img.height + header_h + footer_h), "black")
            img_with_hf.paste(img, (0, header_h))
            img_with_hf.paste(title_img, (0, 0))
            date_txt = get_date(os.path.basename(path))
            draw_footer = ImageDraw.Draw(img_with_hf)
            footer_bbox = draw_footer.textbbox((0, 0), date_txt, font=font)
            x_footer, y_footer = (img_with_hf.width - footer_bbox[2]) // 2, img_with_hf.height - footer_h + (footer_h - footer_bbox[3]) // 2
            draw_footer.text((x_footer, y_footer), date_txt, font=font, fill="white")
            img_array = np.array(img_with_hf)
            if prev_img is not None:
                for fade_img in fade_imgs(prev_img, img_with_hf):
                    writer.append_data(np.array(fade_img))
            writer.append_data(img_array)
            prev_img = img_with_hf
    messagebox.showinfo("Sucesso", f"GIF criado: {out_gif}")
    print("Processamento concluído.")
    root.quit()
    root.destroy()

if __name__ == "__main__":
    main()
