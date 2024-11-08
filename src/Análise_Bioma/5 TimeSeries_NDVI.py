import os
import rasterio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from tkinter import Tk, filedialog, messagebox

# Função que usa o método `askdirectory` da biblioteca `tkinter`
def selecionar_pasta(titulo):
    """
    Abre uma janela para seleção de diretório.
    """
    raiz = Tk()
    raiz.withdraw()  # Oculta a janela principal do Tkinter
    caminho_pasta = filedialog.askdirectory(title=titulo)
    if not caminho_pasta:
        raise ValueError("Nenhuma pasta foi selecionada.")
    return caminho_pasta

# Função principal que usa os métodos `listdir`, `join`, `endswith` da biblioteca `os`,
# e métodos de processamento de dados e detecção de picos de várias bibliotecas
def main():
    """
    Realiza a análise temporal de arquivos TIFF de biomassa, salva a série temporal em CSV
    e plota o gráfico de biomassa com marcações de tendências de crescimento e corte.
    """
    try:
        # Seleção do diretório de entrada e saída
        diretorio_entrada = selecionar_pasta("Selecione a pasta com os arquivos TIFF Biomassa")
        diretorio_saida = selecionar_pasta("Selecione a pasta para salvar o CSV e o gráfico")

        # Obter todos os arquivos TIFF no diretório especificado
        caminhos_arquivos = [os.path.join(diretorio_entrada, f) for f in os.listdir(diretorio_entrada) if f.endswith('.tif')]

        if not caminhos_arquivos:
            messagebox.showerror("Erro", "Nenhum arquivo TIFF foi encontrado no diretório especificado.")
            return

        dados = []

        # Iterar sobre cada arquivo TIFF
        for caminho_arquivo in caminhos_arquivos:
            try:
                data_str = os.path.basename(caminho_arquivo).split('_')[1].replace('Z.tif', '')
                data = pd.to_datetime(data_str, format='%Y-%m-%d')
            except (IndexError, ValueError):
                messagebox.showwarning("Aviso", f"Nome de arquivo inválido ou formato de data incorreto: {caminho_arquivo}")
                continue

            with rasterio.open(caminho_arquivo) as src:
                dados_ndvi = src.read(1)
                # Normalizar os valores de NDVI caso necessário
                if np.max(dados_ndvi) > 1:
                    dados_ndvi = dados_ndvi / 10000  # Normaliza os valores dividindo por 10.000
                media_ndvi = np.nanmean(dados_ndvi)

            dados.append((data, media_ndvi))

        if not dados:
            messagebox.showerror("Erro", "Nenhum dado válido foi encontrado. O processo será encerrado.")
            return

        # Criar DataFrame da série temporal e ordenar por data
        df = pd.DataFrame(dados, columns=['Data', 'Media_NDVI']).sort_values('Data')

        # Salvar a tabela completa (sem exclusões)
        caminho_saida_csv_completo = os.path.join(diretorio_saida, 'serie_temporal_completa.csv')
        df.to_csv(caminho_saida_csv_completo, index=False)
        messagebox.showinfo("Sucesso", f"Tabela completa salva em {caminho_saida_csv_completo}")

        # Calcular o desvio percentual e remover datas com desvios maiores que 100%
        df['Diff_NDVI'] = df['Media_NDVI'].diff().abs()
        df['Percent_Desvio'] = (df['Diff_NDVI'] / df['Media_NDVI'].shift(1)) * 100
        df_filtrado = df[df['Percent_Desvio'] <= 100].drop(['Diff_NDVI', 'Percent_Desvio'], axis=1)

        # Verificar se o DataFrame não está vazio após a filtragem
        if df_filtrado.empty:
            messagebox.showerror("Erro", "Nenhum dado restante após a filtragem dos desvios. O processo será encerrado.")
            return

        # Aplicar a suavização antes de salvar a tabela filtrada
        janela_suavizacao = 9  # Suavização aumentada
        df_filtrado['NDVI_Suavizado'] = df_filtrado['Media_NDVI'].rolling(window=janela_suavizacao, center=True).mean()

        # Salvar a tabela filtrada
        caminho_saida_csv_filtrado = os.path.join(diretorio_saida, 'serie_temporal_filtrada.csv')
        df_filtrado.to_csv(caminho_saida_csv_filtrado, index=False)
        messagebox.showinfo("Sucesso", f"Tabela filtrada salva em {caminho_saida_csv_filtrado}")

        # Parâmetros de detecção
        limite_prominencia = 0.05
        limite_largura = 5

        # Detectar picos e vales usando a biomassa suavizada
        picos, _ = find_peaks(df_filtrado['NDVI_Suavizado'].fillna(0), prominence=limite_prominencia, width=limite_largura)
        vales, _ = find_peaks(-df_filtrado['NDVI_Suavizado'].fillna(0), prominence=limite_prominencia, width=limite_largura)

        # Implementar sequência Crescimento → Pico → Corte com legendas corretas
        tendencias_filtradas = []
        sequencia = "crescimento"  # Começamos esperando um crescimento

        i, j = 0, 0  # Índices para percorrer picos e vales

        while i < len(picos) and j < len(vales):
            if sequencia == "crescimento" and picos[i] < vales[j]:
                tendencias_filtradas.append(('corte', picos[i]))  # Pico corretamente marcado como "corte" na sequência
                sequencia = "pico"
                i += 1
            elif sequencia == "pico" and vales[j] > tendencias_filtradas[-1][1]:
                tendencias_filtradas.append(('crescimento_ou_corte', vales[j]))  # Crescimento/Corte
                sequencia = "crescimento"
                j += 1
            else:
                if sequencia == "crescimento":
                    i += 1
                else:
                    j += 1

        # Adicionar eventos remanescentes no final
        if i < len(picos) and sequencia == "crescimento":
            tendencias_filtradas.append(('corte', picos[i]))
        if j < len(vales) and sequencia == "pico":
            tendencias_filtradas.append(('crescimento_ou_corte', vales[j]))

        # Plotar o gráfico atualizado com picos destacados e legendas corretas
        plt.figure(figsize=(14, 7))
        plt.plot(df_filtrado['Data'], df_filtrado['Media_NDVI'], label='Biomassa Original', alpha=0.5, color='skyblue', linewidth=1.5)
        plt.plot(df_filtrado['Data'], df_filtrado['NDVI_Suavizado'], label='Biomassa Suavizada', color='orange', linewidth=2)

        # Marcar as linhas de Crescimento/Corte e Picos
        legenda_crescimento_corte_adicionada = False
        legenda_pico_adicionada = False

        for rotulo, tendencia in tendencias_filtradas:
            if rotulo == 'crescimento_ou_corte':
                plt.axvline(x=df_filtrado['Data'].iloc[tendencia], color='purple', linestyle='--', linewidth=1.5,
                            label='Crescimento ou Corte' if not legenda_crescimento_corte_adicionada else "")
                legenda_crescimento_corte_adicionada = True
            elif rotulo == 'corte':
                plt.axvline(x=df_filtrado['Data'].iloc[tendencia], color='red', linestyle='-.', linewidth=1.5,
                            label='Pico' if not legenda_pico_adicionada else "")
                legenda_pico_adicionada = True

        # Título e eixos
        plt.title('Série Temporal de Biomassa')
        plt.xlabel('Data')
        plt.ylabel('Biomassa')

        plt.legend(loc='lower left', fontsize='medium', frameon=True)
        plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)

        # Salvar o gráfico
        caminho_saida_imagem = os.path.join(diretorio_saida, 'grafico_biomassa.png')
        plt.savefig(caminho_saida_imagem, dpi=300, bbox_inches='tight')
        messagebox.showinfo("Sucesso", f"Gráfico salvo em {caminho_saida_imagem}")

        plt.show()

    except ValueError as e:
        messagebox.showerror("Erro", str(e))

if __name__ == "__main__":
    main()
