import os
import cv2
import argparse
import logging
from tkinter import Tk, filedialog
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def obter_diretorio_input(titulo):
    """
    Abre uma janela para selecionar o diretório de entrada com imagens.
    """
    raiz = Tk()
    raiz.withdraw()
    diretorio = filedialog.askdirectory(title=titulo)
    if not diretorio:
        logging.error("Nenhum diretório foi selecionado.")
        exit()
    return diretorio

def obter_diretorio_saida():
    """
    Abre uma janela para selecionar o diretório de saída para salvar as imagens processadas.
    """
    raiz = Tk()
    raiz.withdraw()
    diretorio = filedialog.askdirectory(title="Selecione o diretório de saída para as imagens processadas")
    if not diretorio:
        logging.error("Nenhum diretório foi selecionado.")
        exit()
    return diretorio

def aumentar_resolucao_imagem(caminho_entrada, fator_aumento=2, interpolacao=cv2.INTER_LANCZOS4):
    """
    Aumenta a resolução da imagem utilizando uma interpolação mais sofisticada para minimizar a perda de qualidade.
    """
    imagem = cv2.imread(caminho_entrada)
    if imagem is None:
        logging.error(f"Não foi possível abrir a imagem: {caminho_entrada}")
        return None

    nova_largura = imagem.shape[1] * fator_aumento
    nova_altura = imagem.shape[0] * fator_aumento
    nova_imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=interpolacao)

    return Image.fromarray(cv2.cvtColor(nova_imagem, cv2.COLOR_BGR2RGB))

def combinar_imagens(imagem_rgb, imagem_ndvi):
    """
    Combina as imagens RGB e NDVI lado a lado.
    """
    largura_rgb, altura_rgb = imagem_rgb.size
    largura_ndvi, altura_ndvi = imagem_ndvi.size

    # Escolher a maior altura e redimensionar proporcionalmente mantendo qualidade
    altura_maxima = max(altura_rgb, altura_ndvi)
    if altura_rgb != altura_maxima:
        fator_aumento = altura_maxima / altura_rgb
        nova_largura = int(largura_rgb * fator_aumento)
        imagem_rgb = imagem_rgb.resize((nova_largura, altura_maxima), Image.LANCZOS)

    if altura_ndvi != altura_maxima:
        fator_aumento = altura_maxima / altura_ndvi
        nova_largura = int(largura_ndvi * fator_aumento)
        imagem_ndvi = imagem_ndvi.resize((nova_largura, altura_maxima), Image.LANCZOS)

    # Combina as imagens lado a lado
    largura_combinada = imagem_rgb.width + imagem_ndvi.width
    imagem_combinada = Image.new("RGB", (largura_combinada, altura_maxima))
    imagem_combinada.paste(imagem_rgb, (0, 0))
    imagem_combinada.paste(imagem_ndvi, (imagem_rgb.width, 0))

    return imagem_combinada

def adicionar_cabecalho_e_rodape(imagem, texto_cabecalho, texto_rodape, proporcao_altura_cabecalho=0.1, proporcao_altura_rodape=0.1):
    """
    Adiciona cabeçalho e rodapé à imagem combinada.
    """
    altura_cabecalho = int(imagem.height * proporcao_altura_cabecalho)
    altura_rodape = int(imagem.height * proporcao_altura_rodape)

    # Cria o cabeçalho e o rodapé como fundos brancos
    cabecalho = Image.new("RGB", (imagem.width, altura_cabecalho), (255, 255, 255))
    rodape = Image.new("RGB", (imagem.width, altura_rodape), (255, 255, 255))

    # Desenha o texto no cabeçalho e no rodapé
    desenhar_cabecalho = ImageDraw.Draw(cabecalho)
    desenhar_rodape = ImageDraw.Draw(rodape)

    try:
        fonte = ImageFont.truetype("arial.ttf", int(altura_cabecalho * 0.5))
    except IOError:
        fonte = ImageFont.load_default()

    # Centraliza o texto do cabeçalho
    caixa_texto_cabecalho = desenhar_cabecalho.textbbox((0, 0), texto_cabecalho, font=fonte)
    largura_texto_cabecalho = caixa_texto_cabecalho[2] - caixa_texto_cabecalho[0]
    altura_texto_cabecalho = caixa_texto_cabecalho[3] - caixa_texto_cabecalho[1]
    posicao_texto_cabecalho = ((cabecalho.width - largura_texto_cabecalho) // 2, (cabecalho.height - altura_texto_cabecalho) // 2)
    desenhar_cabecalho.text(posicao_texto_cabecalho, texto_cabecalho, font=fonte, fill=(0, 0, 0))

    # Centraliza o texto do rodapé
    caixa_texto_rodape = desenhar_rodape.textbbox((0, 0), texto_rodape, font=fonte)
    largura_texto_rodape = caixa_texto_rodape[2] - caixa_texto_rodape[0]
    altura_texto_rodape = caixa_texto_rodape[3] - caixa_texto_rodape[1]
    posicao_texto_rodape = ((rodape.width - largura_texto_rodape) // 2, (rodape.height - altura_texto_rodape) // 2)
    desenhar_rodape.text(posicao_texto_rodape, texto_rodape, font=fonte, fill=(0, 0, 0))

    # Combina cabeçalho, imagem e rodapé verticalmente
    imagem_final = Image.new("RGB", (imagem.width, cabecalho.height + imagem.height + rodape.height))
    imagem_final.paste(cabecalho, (0, 0))
    imagem_final.paste(imagem, (0, cabecalho.height))
    imagem_final.paste(rodape, (0, cabecalho.height + imagem.height))

    return imagem_final

def processar_imagens(diretorio_entrada, diretorio_ndvi, diretorio_saida, texto_cabecalho, fator_aumento=2):
    """
    Processa imagens RGB e NDVI, combinando-as e adicionando cabeçalho e rodapé.
    """
    for nome_arquivo in sorted(os.listdir(diretorio_entrada)):
        if nome_arquivo.lower().endswith('.png'):
            caminho_rgb = os.path.join(diretorio_entrada, nome_arquivo)
            caminho_ndvi = os.path.join(diretorio_ndvi, nome_arquivo)

            if os.path.exists(caminho_ndvi):
                imagem_rgb = aumentar_resolucao_imagem(caminho_rgb, fator_aumento)
                imagem_ndvi = aumentar_resolucao_imagem(caminho_ndvi, fator_aumento)

                if imagem_rgb is None or imagem_ndvi is None:
                    continue

                imagem_combinada = combinar_imagens(imagem_rgb, imagem_ndvi)
                if imagem_combinada is None:
                    continue

                # Extrai a data do nome do arquivo ou usa um padrão
                texto_data = extrair_data_do_nome_arquivo(nome_arquivo)
                imagem_final = adicionar_cabecalho_e_rodape(imagem_combinada, texto_cabecalho, texto_data)

                caminho_saida = os.path.join(diretorio_saida, f"combinado_{nome_arquivo}")
                imagem_final.save(caminho_saida)
                logging.info(f"Imagem processada e salva em: {caminho_saida}")
            else:
                logging.warning(f"Imagem NDVI correspondente não encontrada para: {nome_arquivo}")

def extrair_data_do_nome_arquivo(nome_arquivo):
    """
    Extrai a data do nome do arquivo baseado no padrão 'exemplo_YYYYMMDDZ_outro.png'.
    """
    try:
        return nome_arquivo.split('_')[1].split('Z')[0]
    except IndexError:
        return "Data desconhecida"

def main():
    parser = argparse.ArgumentParser(description="Script para aumentar a resolução de imagens PNG e combinar imagens RGB e NDVI de maneira automática e prática.")
    parser.add_argument('-f', '--fator', type=int, default=2, help="Fator de aumento da resolução. Exemplo: 2 para dobrar a resolução.")
    args = parser.parse_args()

    diretorio_input = obter_diretorio_input("Selecione o diretório com as imagens RGB")
    diretorio_ndvi = obter_diretorio_input("Selecione o diretório com as imagens NDVI")
    diretorio_saida = obter_diretorio_saida()

    print("Digite o título para o cabeçalho:")
    texto_cabecalho = input("Digite o título para o cabeçalho: ")

    processar_imagens(diretorio_input, diretorio_ndvi, diretorio_saida, texto_cabecalho, fator_aumento=args.fator)

if __name__ == "__main__":
    main()
