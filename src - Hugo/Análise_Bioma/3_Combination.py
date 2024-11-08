import os
import cv2
import logging
from tkinter import Tk, filedialog
from PIL import Image, ImageDraw, ImageFont
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_dir(title):
    raiz = Tk()
    raiz.withdraw()
    dir = filedialog.askdirectory(title=title)
    if not dir:
        logging.error("Nenhum diretório selecionado.")
        exit()
    return dir

def resize_img(path, scale=2, interp=cv2.INTER_LANCZOS4):
    img = cv2.imread(path)
    if img is None:
        logging.error(f"Erro ao abrir imagem: {path}")
        return None
    new_w, new_h = img.shape[1] * scale, img.shape[0] * scale
    return Image.fromarray(cv2.cvtColor(cv2.resize(img, (new_w, new_h), interpolation=interp), cv2.COLOR_BGR2RGB))

def combine_imgs(rgb, ndvi):
    max_height = max(rgb.size[1], ndvi.size[1])
    if rgb.size[1] != max_height:
        scale = max_height / rgb.size[1]
        rgb = rgb.resize((int(rgb.size[0] * scale), max_height), Image.LANCZOS)
    if ndvi.size[1] != max_height:
        scale = max_height / ndvi.size[1]
        ndvi = ndvi.resize((int(ndvi.size[0] * scale), max_height), Image.LANCZOS)
    combined = Image.new("RGB", (rgb.width + ndvi.width, max_height))
    combined.paste(rgb, (0, 0))
    combined.paste(ndvi, (rgb.width, 0))
    return combined

def add_header_footer(img, header_text, footer_text, header_ratio=0.1, footer_ratio=0.1):
    header_h = int(img.height * header_ratio)
    footer_h = int(img.height * footer_ratio)
    header = Image.new("RGB", (img.width, header_h), (255, 255, 255))
    footer = Image.new("RGB", (img.width, footer_h), (255, 255, 255))
    draw_header, draw_footer = ImageDraw.Draw(header), ImageDraw.Draw(footer)
    try:
        font = ImageFont.truetype("arial.ttf", int(header_h * 0.5))
    except IOError:
        font = ImageFont.load_default()
    header_box = draw_header.textbbox((0, 0), header_text, font=font)
    header_pos = ((header.width - (header_box[2] - header_box[0])) // 2, (header.height - (header_box[3] - header_box[1])) // 2)
    draw_header.text(header_pos, header_text, font=font, fill=(0, 0, 0))
    footer_box = draw_footer.textbbox((0, 0), footer_text, font=font)
    footer_pos = ((footer.width - (footer_box[2] - footer_box[0])) // 2, (footer.height - (footer_box[3] - footer_box[1])) // 2)
    draw_footer.text(footer_pos, footer_text, font=font, fill=(0, 0, 0))
    final_img = Image.new("RGB", (img.width, header.height + img.height + footer.height))
    final_img.paste(header, (0, 0))
    final_img.paste(img, (0, header.height))
    final_img.paste(footer, (0, header.height + img.height))
    return final_img

def process_imgs(input_dir, ndvi_dir, out_dir, header_txt, scale=2):
    for file in sorted(os.listdir(input_dir)):
        if file.lower().endswith('.png'):
            rgb_path, ndvi_path = os.path.join(input_dir, file), os.path.join(ndvi_dir, file)
            if os.path.exists(ndvi_path):
                rgb_img = resize_img(rgb_path, scale)
                ndvi_img = resize_img(ndvi_path, scale)
                if rgb_img is None or ndvi_img is None:
                    continue
                combined_img = combine_imgs(rgb_img, ndvi_img)
                if combined_img is None:
                    continue
                date_text = extract_date(file)
                final_img = add_header_footer(combined_img, header_txt, date_text)
                save_path = os.path.join(out_dir, f"combinado_{file}")
                final_img.save(save_path)
                logging.info(f"Imagem salva: {save_path}")
            else:
                logging.warning(f"Imagem NDVI não encontrada: {file}")

def extract_date(file_name):
    try:
        return file_name.split('_')[1].split('Z')[0]
    except IndexError:
        return "Data desconhecida"

def run():
    parser = argparse.ArgumentParser(description="Aumenta resolução e combina imagens RGB e NDVI.")
    parser.add_argument('-f', '--fator', type=int, default=2, help="Fator de aumento da resolução.")
    args = parser.parse_args()
    dir_rgb = get_dir("Selecionar diretório RGB")
    dir_ndvi = get_dir("Selecionar diretório NDVI")
    dir_out = get_dir("Selecionar diretório de saída")
    print("Digite o cabeçalho:")
    header = input("Digite o cabeçalho: ")
    process_imgs(dir_rgb, dir_ndvi, dir_out, header, scale=args.fator)

if __name__ == "__main__":
    run()
