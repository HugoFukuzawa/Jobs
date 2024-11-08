from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np
import os
import re
from tkinter import Tk, filedialog, messagebox

# Configurações iniciais
header_height = 50
footer_height = 50
fade_frames = 20
duration_per_frame = 2  # Duração de cada imagem em segundos
resize_to = (800, 800)  # Tamanho máximo para redimensionamento
font_path = "arial.ttf"  # Altere o caminho da fonte Arial se necessário

# Função para extrair a data do nome do arquivo
def extract_date_from_filename(filename):
    cleaned_filename = filename.replace('combined_openEO_', '')
    match = re.search(r'(\d{4}-\d{2}-\d{2})', cleaned_filename)
    return match.group(1) if match else "Data Desconhecida"

# Função para criar transição de fade entre duas imagens
def create_fade_transition(image1, image2, steps=fade_frames):
    if image1.size != image2.size:
        image2 = image2.resize(image1.size, Image.Resampling.LANCZOS)

    fade_images = []
    for i in range(steps + 1):
        alpha = i / float(steps)
        blended = Image.blend(image1, image2, alpha)
        fade_images.append(blended)
    return fade_images

def main():
    # Interface gráfica para seleção de diretórios
    root = Tk()
    root.withdraw()

    input_folder = filedialog.askdirectory(title="Selecione a pasta com as imagens PNG combinadas")
    if not input_folder:
        messagebox.showerror("Erro", "Pasta de entrada não selecionada.")
        root.destroy()
        return

    output_folder = filedialog.askdirectory(title="Selecione a pasta para salvar o GIF")
    if not output_folder:
        messagebox.showerror("Erro", "Pasta de saída não selecionada.")
        root.destroy()
        return

    # Mensagem de início de processamento
    print("Processamento iniciado (este processo pode demorar um pouco...) Processando...")

    output_gif_path = os.path.join(output_folder, "biomassa_analysis.gif")

    # Obter lista de arquivos PNG no diretório selecionado
    image_paths = [os.path.join(input_folder, file) for file in sorted(os.listdir(input_folder)) if file.endswith('.png')]
    if not image_paths:
        messagebox.showerror("Erro", "Nenhuma imagem PNG foi encontrada na pasta fornecida.")
        root.destroy()
        return

    # Carregar fontes para adicionar textos
    try:
        font = ImageFont.truetype(font_path, 20)
        title_font = ImageFont.truetype(font_path, 24)
    except IOError:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Configurar cabeçalho e rodapé uma vez para reuso
    title_text = "Análise de Biomassa - Centro de Tecnologia Canavieira (CTC)"
    title_image = Image.new("RGB", (resize_to[0], header_height), "black")
    draw_title = ImageDraw.Draw(title_image)
    title_width, title_height = draw_title.textbbox((0, 0), title_text, font=title_font)[2:]
    x_title = (title_image.width - title_width) // 2
    y_title = (header_height - title_height) // 2
    draw_title.text((x_title, y_title), title_text, font=title_font, fill="white")

    with imageio.get_writer(output_gif_path, mode='I', duration=duration_per_frame) as writer:
        previous_image = None
        for image_path in image_paths:
            # Carregar e redimensionar imagem principal
            image = Image.open(image_path)
            if image.size != resize_to:
                image.thumbnail(resize_to, Image.Resampling.LANCZOS)

            # Criar imagem com espaço para cabeçalho e rodapé
            image_with_header_footer = Image.new("RGB", (image.width, image.height + header_height + footer_height), "black")
            image_with_header_footer.paste(image, (0, header_height))

            # Inserir título no cabeçalho
            image_with_header_footer.paste(title_image, (0, 0))

            # Extrair e adicionar data no rodapé
            date_text = extract_date_from_filename(os.path.basename(image_path))
            draw_footer = ImageDraw.Draw(image_with_header_footer)
            date_width, date_height = draw_footer.textbbox((0, 0), date_text, font=font)[2:]
            x_date = (image_with_header_footer.width - date_width) // 2
            y_date = image_with_header_footer.height - footer_height + (footer_height - date_height) // 2
            draw_footer.text((x_date, y_date), date_text, font=font, fill="white")

            # Converter a imagem para um array NumPy e adicionar ao GIF com efeito de fade
            image_array = np.array(image_with_header_footer)
            if previous_image is not None:
                fade_images = create_fade_transition(previous_image, image_with_header_footer)
                for fade_image in fade_images:
                    writer.append_data(np.array(fade_image))

            writer.append_data(image_array)
            previous_image = image_with_header_footer

    # Exibir mensagem de conclusão e garantir o encerramento completo
    messagebox.showinfo("Sucesso", f"GIF criado com sucesso: {output_gif_path}")
    print("Processamento concluído com sucesso.")
    root.quit()  # Finaliza o loop do Tkinter
    root.destroy()  # Garante o fechamento da janela

if __name__ == "__main__":
    main()