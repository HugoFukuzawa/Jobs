import os
import geopandas as gpd
import openeo
import logging
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from datetime import datetime
from tkinter import Tk, filedialog, simpledialog, messagebox
from openeo.rest.auth.config import RefreshTokenStore
from rasterio.plot import show
from matplotlib.colors import LinearSegmentedColormap
from pyproj import Transformer

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Funções auxiliares para autenticação e limpeza de tokens
def clear_refresh_token():
    """Limpa tokens de atualização para resolver problemas de autenticação."""
    logger.info("Limpando tokens de atualização para resolver problemas de autenticação...")
    RefreshTokenStore().remove()
    logger.info("Tokens de atualização limpos com sucesso.")


def connect_and_authenticate(url):
    """Conecta-se ao back-end do openEO e autentica o usuário."""
    try:
        connection = openeo.connect(url=url)
        connection.authenticate_oidc()
        logger.info(f"Conectado ao openEO no URL: {url}")
        return connection
    except openeo.rest.auth.AuthException as e:
        logger.warning(f"Erro de autenticação: {e}. Tentando limpar o token e autenticar novamente.")
        clear_refresh_token()
        connection = openeo.connect(url=url)
        connection.authenticate_oidc()
        logger.info(f"Reconectado ao openEO no URL: {url} após limpar o token.")
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ou autenticar: {e}")
        raise


# Funções principais para processar o NDVI
def find_shapefile_in_directory(directory):
    """Procura por um arquivo shapefile (.shp) no diretório especificado."""
    for file in os.listdir(directory):
        if file.endswith(".shp"):
            return os.path.join(directory, file)
    raise FileNotFoundError(f"Nenhum arquivo shapefile (.shp) encontrado no diretório {directory}")


def define_fields(shapefile_path):
    """Lê o shapefile e o reprojeta para EPSG:4326."""
    return gpd.read_file(shapefile_path).to_crs("EPSG:4326")


def get_bounding_box(geo_df):
    """Obtém a extensão espacial (bounding box) do GeoDataFrame."""
    bounds = geo_df.total_bounds
    return {
        "west": bounds[0],
        "south": bounds[1],
        "east": bounds[2],
        "north": bounds[3],
    }


def load_ndvi_data(connection, spatial_extent, start_date, end_date):
    """Carrega os dados da coleção Sentinel-2 Level 2A e calcula o NDVI manualmente."""
    try:
        cube_s2 = connection.load_collection(
            "SENTINEL2_L2A",
            spatial_extent=spatial_extent,
            temporal_extent=[start_date, end_date],
            bands=["B08", "B04"],
            max_cloud_cover=15
        )
        if cube_s2 is None:
            logger.error("Erro ao carregar a coleção Sentinel-2. A coleção está vazia.")
            raise ValueError("A coleção Sentinel-2 não pôde ser carregada corretamente.")

        # Calcula o NDVI manualmente
        cube_s2_ndvi = cube_s2.apply(lambda x: (x["B08"] - x["B04"]) / (x["B08"] + x["B04"]))
        return cube_s2_ndvi
    except Exception as e:
        logger.error(f"Erro ao carregar os dados do Sentinel-2 e calcular o NDVI: {e}")
        raise


def process_data_cube(cube_s2_ndvi):
    """Salva a série temporal como uma coleção de imagens GeoTIFF e cria um job para processamento."""
    try:
        result = cube_s2_ndvi.save_result(format="GTIFF", options={"output_band": "NDVI"})
        job = result.create_job(title="ndvi_time_series")
        logger.info(f"Job '{job.job_id}' criado com sucesso para processamento em back-end.")
        job.start_and_wait()
        if job.status() != "finished":
            logger.error(f"Erro no processamento do job '{job.job_id}'. Status final: {job.status()}.")
            raise ValueError(f"Job '{job.job_id}' não foi concluído com sucesso.")
        logger.info(f"Job '{job.job_id}' concluído com sucesso.")
        return job
    except Exception as e:
        logger.error(f"Erro ao criar ou processar o job para o NDVI: {e}")
        raise


def download_results(job, output_path):
    """Baixa os resultados do job e os salva no diretório especificado."""
    try:
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        job.get_results().download_files(target=output_path)
        logger.info(f"Resultados baixados e salvos no diretório {output_path}")
    except Exception as e:
        logger.error(f"Erro ao baixar os resultados do job '{job.job_id}': {e}")
        raise


def convert_ndvi_to_colored_png(tiff_path, png_output_path):
    """Converte um arquivo GeoTIFF NDVI em um PNG colorido com latitude e longitude."""
    try:
        cmap = plt.get_cmap('RdYlGn')
        value_range = (-1, 1)  # Intervalo original do NDVI
        color_label = 'NDVI'
        with rasterio.open(tiff_path) as src:
            ndvi_array = src.read(1)
            if ndvi_array is None or ndvi_array.size == 0:
                logger.error(f"O arquivo TIFF '{tiff_path}' está vazio ou não contém dados válidos.")
                raise ValueError(f"Arquivo TIFF vazio: {tiff_path}")

            # Verificar se todos os valores do NDVI são nulos ou mascarados
            if np.all(np.isnan(ndvi_array)) or np.all(ndvi_array == src.nodata):
                logger.error(f"O arquivo TIFF '{tiff_path}' contém apenas valores nulos ou não válidos.")
                raise ValueError(f"Arquivo TIFF sem dados NDVI válidos: {tiff_path}")

            # Logar os valores mínimos e máximos do NDVI para verificar possíveis problemas
            min_ndvi = np.nanmin(ndvi_array)
            max_ndvi = np.nanmax(ndvi_array)
            logger.info(f"Valores do NDVI - mínimo: {min_ndvi}, máximo: {max_ndvi}")

            if min_ndvi == max_ndvi:
                logger.warning(f"Os valores do NDVI no arquivo '{tiff_path}' são constantes ({min_ndvi}). A imagem pode aparecer sem contraste.")

            transform = src.transform
            crs_raster = src.crs
            transformer = Transformer.from_crs(crs_raster, "EPSG:4326", always_xy=True)

            # Normaliza o NDVI para o intervalo [0, 1]
            ndvi_normalized = (ndvi_array - value_range[0]) / (value_range[1] - value_range[0])
            ndvi_normalized = np.clip(ndvi_normalized, 0, 1)  # Garantir que os valores estão no intervalo [0, 1]
            ndvi_normalized = np.ma.masked_where((ndvi_array < value_range[0]) | (ndvi_array > value_range[1]), ndvi_normalized)

            fig, ax = plt.subplots(figsize=(10, 10))
            cax = ax.imshow(ndvi_normalized, cmap=cmap, vmin=0, vmax=1, interpolation='none')
            color_bar = fig.colorbar(cax, ax=ax, orientation='vertical')
            color_bar.set_label(color_label, fontsize=12)

            # Definir coordenadas de longitude e latitude nos ticks
            x_ticks = np.linspace(0, ndvi_array.shape[1], num=5)
            y_ticks = np.linspace(0, ndvi_array.shape[0], num=5)
            x_coords = [transform * (x, 0) for x in x_ticks]
            y_coords = [transform * (0, y) for y in y_ticks]
            lon_coords, lat_coords = zip(*[transformer.transform(x[0], y[1]) for x, y in zip(x_coords, y_coords)])
            ax.set_xticks(x_ticks)
            ax.set_xticklabels([f"{lon:.4f}" for lon in lon_coords])
            ax.set_yticks(y_ticks)
            ax.set_yticklabels([f"{lat:.4f}" for lat in lat_coords])
            ax.set_xlabel('Longitude (degrees)')
            ax.set_ylabel('Latitude (degrees)')

            if os.path.exists(png_output_path):
                os.remove(png_output_path)
                logger.info(f"Existing file removed: {png_output_path}")

            plt.savefig(png_output_path, format='png', dpi=300, bbox_inches='tight')
            plt.close()
        logger.info(f"NDVI image with coloring and coordinates converted and saved as: {png_output_path}")
    except Exception as e:
        logger.error(f"Error converting the file {tiff_path}: {e}")


def process_all_ndvi_tiffs(input_directory, output_directory):
    """Processa todos os arquivos GeoTIFF NDVI no diretório de entrada e os converte em PNGs coloridos."""
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    for file_name in os.listdir(input_directory):
        if file_name.lower().endswith('.tif'):
            tiff_path = os.path.join(input_directory, file_name)
            png_output_path = os.path.join(output_directory, f"{os.path.splitext(file_name)[0]}.png")
            logger.info(f"Processando {file_name} como NDVI...")
            convert_ndvi_to_colored_png(tiff_path, png_output_path)


def main():
    """Função principal que coordena o fluxo de trabalho."""
    root = Tk()
    root.withdraw()

    directory = filedialog.askdirectory(title="Selecione o diretório do shapefile da área de interesse")
    if not directory:
        messagebox.showerror("Erro", "Nenhum diretório selecionado para o shapefile.")
        return

    output_dir = filedialog.askdirectory(title="Selecione o diretório para salvar os resultados")
    if not output_dir:
        messagebox.showerror("Erro", "Nenhum diretório selecionado para salvar os resultados.")
        return

    start_date = simpledialog.askstring("Data de Início", "Insira a data de início (YYYY-MM-DD):")
    if not start_date:
        messagebox.showerror("Erro", "Data de início não fornecida.")
        return

    end_date = simpledialog.askstring("Data de Término", "Insira a data de término (YYYY-MM-DD):")
    if not end_date:
        messagebox.showerror("Erro", "Data de término não fornecida.")
        return

    url = "https://openeo.dataspace.copernicus.eu"
    try:
        connection = connect_and_authenticate(url)
        shapefile_path = find_shapefile_in_directory(directory)
        fields = define_fields(shapefile_path)
        spatial_extent = get_bounding_box(fields)

        # Carrega e processa o cubo de dados para calcular o NDVI
        cube_s2_ndvi = load_ndvi_data(connection, spatial_extent, start_date, end_date)
        job = process_data_cube(cube_s2_ndvi)

        # Baixa os resultados da série e converte diretamente para PNG
        download_results(job, output_dir)
        process_all_ndvi_tiffs(output_dir, output_dir)

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        messagebox.showerror("Erro", f"Erro no processamento: {e}")


if __name__ == '__main__':
    main()
