import os
import geopandas as gpd
import openeo
import logging
import rasterio
import numpy as np
from rasterio.enums import Resampling
from PIL import Image
from tkinter import Tk, filedialog

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_and_authenticate(url):
    """
    Conecta e autentica no serviço OpenEO.
    """
    try:
        connection = openeo.connect(url=url)
        connection.authenticate_oidc()
        logger.info(f"Conectado ao OpenEO no URL: {url}")
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ou autenticar: {e}")
        raise

def find_shapefile_in_directory(directory):
    """
    Procura por arquivos .shp em um diretório.
    """
    for file in os.listdir(directory):
        if file.endswith(".shp"):
            return os.path.join(directory, file)
    raise FileNotFoundError(f"Nenhum arquivo shapefile (.shp) encontrado no diretório {directory}")

def define_fields(shapefile_path):
    """
    Lê o shapefile e converte para WGS84 (EPSG:4326).
    """
    return gpd.read_file(shapefile_path).to_crs("EPSG:4326")

def get_bounding_box(geo_df):
    """
    Obtém o bounding box, limitado aos limites do Brasil.
    """
    bounds = geo_df.total_bounds
    return {
        "west": max(bounds[0], -74),
        "south": max(bounds[1], -33),
        "east": min(bounds[2], -34),
        "north": min(bounds[3], 5),
    }

def load_rgb_data(connection, spatial_extent, start_date, end_date):
    """
    Carrega os dados Sentinel-2 (RGB) com intervalo de tempo especificado.
    """
    temporal_extent = [start_date, end_date]
    return connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["B04", "B03", "B02"],  # B04: Red, B03: Green, B02: Blue
        max_cloud_cover=50
    )

def execute_batch_job(cube, output_format="GTIFF", job_title="RGB Time Series"):
    """
    Executa o job em lote para processamento.
    """
    job = cube.execute_batch(
        out_format=output_format,
        title=job_title,
        format_options={"cloud_optimized": True}
    )
    logger.info("Job iniciado com ID: %s", job.job_id)
    return job

def download_results(job, output_path):
    """
    Baixa todos os arquivos resultantes do job em lote.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    job.download_results(target=output_path)
    logger.info(f"Série temporal de GeoTIFFs baixada e salva no diretório {output_path}")

def rescale_to_8bit(array, min_val=None, max_val=None):
    """
    Reescala uma matriz de valores para 8 bits (0-255).
    """
    if min_val is None:
        min_val = np.nanpercentile(array, 2)
    if max_val is None:
        max_val = np.nanpercentile(array, 98)

    scaled = 255 * (array - min_val) / (max_val - min_val)
    return np.clip(scaled, 0, 255).astype(np.uint8)

def convert_geotiff_to_png(geotiff_files, output_dir):
    """
    Converte os arquivos GeoTIFF para PNG.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for file in geotiff_files:
        with rasterio.open(file) as src:
            red = src.read(1, resampling=Resampling.nearest)
            green = src.read(2, resampling=Resampling.nearest)
            blue = src.read(3, resampling=Resampling.nearest)

            red = rescale_to_8bit(red)
            green = rescale_to_8bit(green)
            blue = rescale_to_8bit(blue)

            rgb = np.stack((red, green, blue), axis=-1)
            output_file = os.path.join(output_dir, os.path.basename(file).replace('.tif', '.png'))
            Image.fromarray(rgb).save(output_file)

        logger.info(f"Imagem convertida para PNG e salva em: {output_file}")

def main():
    """
    Executa o fluxo principal para criar uma série temporal de imagens RGB.
    """
    # Abrir a janela de seleção de arquivos com tkinter
    root = Tk()
    root.withdraw()  # Ocultar a janela principal do Tkinter

    # Selecionar diretório que contém o shapefile
    directory = filedialog.askdirectory(title="Selecione o diretório do shapefile da área de interesse")
    output_dir = filedialog.askdirectory(title="Selecione o diretório para salvar os resultados")

    # Intervalo temporal
    start_date = input("Insira a data de início (YYYY-MM-DD): ")
    end_date = input("Insira a data de término (YYYY-MM-DD): ")

    url = "openeo.dataspace.copernicus.eu"
    connection = connect_and_authenticate(url)

    shapefile_path = find_shapefile_in_directory(directory)
    fields = define_fields(shapefile_path)
    spatial_extent = get_bounding_box(fields)

    # Carregar os dados Sentinel-2 com as bandas RGB
    data_cube = load_rgb_data(connection, spatial_extent, start_date, end_date)

    # Executar o job em lote
    job = execute_batch_job(data_cube, "GTIFF", "RGB Time Series")

    # Aguardar a conclusão do job e baixar os resultados
    download_results(job, output_dir)

    # Converter os arquivos GeoTIFF para PNG
    geotiff_files = [os.path.join(output_dir, file) for file in os.listdir(output_dir) if file.endswith(".tif")]
    convert_geotiff_to_png(geotiff_files, output_dir)
    logger.info("Conversão de GeoTIFF para PNG concluída com sucesso.")

if __name__ == "__main__":
    main()
