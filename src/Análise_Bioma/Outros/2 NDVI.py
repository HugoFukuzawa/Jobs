import os
import geopandas as gpd
import openeo
import logging
import rasterio
import numpy as np
from rasterio.enums import Resampling
import matplotlib.pyplot as plt
from pyproj import Transformer
from tkinter import Tk, filedialog

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_and_authenticate(url):
    try:
        connection = openeo.connect(url=url)
        connection.authenticate_oidc()
        logger.info(f"Conectado ao OpenEO no URL: {url}")
        return connection
    except Exception as e:
        logger.error(f"Erro ao conectar ou autenticar: {e}")
        raise

def find_shapefile_in_directory(directory):
    for file in os.listdir(directory):
        if file.endswith(".shp"):
            return os.path.join(directory, file)
    raise FileNotFoundError(f"Nenhum arquivo shapefile (.shp) encontrado no diretório {directory}")

def define_fields(shapefile_path):
    return gpd.read_file(shapefile_path).to_crs("EPSG:4326")

def get_bounding_box(geo_df):
    bounds = geo_df.total_bounds
    return {
        "west": max(bounds[0], -74),
        "south": max(bounds[1], -33),
        "east": min(bounds[2], -34),
        "north": min(bounds[3], 5),
    }

def load_ndvi_data(connection, spatial_extent, start_date, end_date):
    temporal_extent = [start_date, end_date]
    return connection.load_collection(
        "SENTINEL2_L2A",
        temporal_extent=temporal_extent,
        spatial_extent=spatial_extent,
        bands=["B08", "B04"],
        max_cloud_cover=50
    )

def calculate_ndvi_and_execute_job(cube, output_format="GTIFF", job_title="NDVI Time Series"):
    nir = cube.band("B08")
    red = cube.band("B04")
    ndvi = (nir - red) / (nir + red)

    job = ndvi.execute_batch(
        out_format=output_format,
        title=job_title,
        format_options={"cloud_optimized": True}
    )
    logger.info("Job iniciado com ID: %s", job.job_id)
    return job

def download_results(job, output_path):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    job.download_results(target=output_path)
    logger.info(f"Série temporal de GeoTIFFs baixada e salva no diretório {output_path}")

def convert_ndvi_to_colored_png(tiff_path, output_png_path):
    try:
        cmap = plt.colormaps.get_cmap('RdYlGn')
        value_range = (0, 1)
        color_label = 'Biomassa'

        with rasterio.open(tiff_path) as src:
            ndvi_array = src.read(1)
            transform = src.transform
            raster_crs = src.crs
            transformer = Transformer.from_crs(raster_crs, "EPSG:4326", always_xy=True)

            ndvi_array = np.ma.masked_where((ndvi_array < value_range[0]) | (ndvi_array > value_range[1]), ndvi_array)

            fig, ax = plt.subplots(figsize=(10, 10))
            cax = ax.imshow(ndvi_array, cmap=cmap, vmin=value_range[0], vmax=value_range[1], interpolation='none')
            cbar = fig.colorbar(cax, ax=ax, orientation='vertical')
            cbar.set_label(color_label, fontsize=12)

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

            if os.path.exists(output_png_path):
                os.remove(output_png_path)
                logger.info(f"Arquivo existente removido: {output_png_path}")

            plt.savefig(output_png_path, format='png', dpi=300, bbox_inches='tight')
            plt.close()

        logger.info(f"Imagem NDVI com coloração e coordenadas convertida e salva como: {output_png_path}")
    except Exception as e:
        logger.error(f"Erro ao converter o arquivo {tiff_path}: {e}")

def process_all_ndvi_tiffs(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith('.tif'):
            tiff_path = os.path.join(input_dir, file_name)
            output_png_path = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}.png")
            logger.info(f"Processando {file_name} como NDVI...")
            convert_ndvi_to_colored_png(tiff_path, output_png_path)

def main():
    root = Tk()
    root.withdraw()

    directory = filedialog.askdirectory(title="Selecione o diretório do shapefile")
    output_dir = filedialog.askdirectory(title="Selecione o diretório para salvar os resultados")

    start_date = input("Insira a data de início (YYYY-MM-DD): ")
    end_date = input("Insira a data de término (YYYY-MM-DD): ")

    url = "openeo.dataspace.copernicus.eu"
    connection = connect_and_authenticate(url)

    shapefile_path = find_shapefile_in_directory(directory)
    fields = define_fields(shapefile_path)
    spatial_extent = get_bounding_box(fields)

    data_cube = load_ndvi_data(connection, spatial_extent, start_date, end_date)
    job = calculate_ndvi_and_execute_job(data_cube, "GTIFF", "NDVI Time Series")

    download_results(job, output_dir)
    geotiff_files = [os.path.join(output_dir, file) for file in os.listdir(output_dir) if file.endswith(".tif")]
    process_all_ndvi_tiffs(output_dir, output_dir)
    logger.info("Conversão de NDVI GeoTIFF para PNG com coloração concluída com sucesso.")

if __name__ == "__main__":
    main()
