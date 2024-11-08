import os
import geopandas as gpd
import openeo
import logging
from datetime import datetime
from tkinter import Tk, filedialog, simpledialog, messagebox
from openeo.rest.auth.config import RefreshTokenStore
from PIL import Image
import rasterio
import numpy as np
from tqdm import tqdm

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def load_rgb_data(connection, spatial_extent, start_date, end_date, max_cloud_cover=15):
    """Carrega os dados da coleção Sentinel-2 Level 2A e seleciona as bandas RGB."""
    cube_s2 = connection.load_collection(
        "SENTINEL2_L2A",
        spatial_extent=spatial_extent,
        temporal_extent=[start_date, end_date],
        bands=["B04", "B03", "B02"],  # Bandas para RGB
        max_cloud_cover=max_cloud_cover
    )
    return cube_s2


def process_data_cube(cube_s2_rgb):
    """Salva a série temporal como uma coleção de imagens GeoTIFF e cria um job para processamento."""
    result = cube_s2_rgb.save_result(format="GTIFF", options={"output_band": "RGB"})
    job = result.create_job(title="rgb_time_series")
    logger.info(f"Job '{job.job_id}' criado com sucesso para processamento em back-end.")
    job.start_and_wait()
    logger.info(f"Job '{job.job_id}' concluído com sucesso.")
    return job


def download_results(job, output_path):
    """Baixa os resultados do job e os salva no diretório especificado."""
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    job.get_results().download_files(target=output_path)
    logger.info(f"Resultados baixados e salvos no diretório {output_path}")


def rename_files_with_metadata(output_path):
    """Renomeia os arquivos baixados com base nas datas correspondentes extraídas dos metadados."""
    files = [f for f in os.listdir(output_path) if f.endswith(".tif")]
    for file in files:
        with rasterio.open(os.path.join(output_path, file)) as dataset:
            try:
                date_str = dataset.tags().get('TIFFTAG_DATETIME')
                if date_str:
                    date = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    new_name = f"RGB_{date.strftime('%Y-%m-%d')}.tif"
                    os.rename(os.path.join(output_path, file), os.path.join(output_path, new_name))
                    logger.info(f"Arquivo renomeado para {new_name}")
            except Exception as e:
                logger.warning(f"Não foi possível renomear o arquivo {file}: {e}")


def linear_scale_range(x, input_min, input_max, output_min=0, output_max=255):
    """Realiza uma transformação linear entre o intervalo de entrada e o intervalo de saída."""
    x = np.clip(x, input_min, input_max)  # Garante que x esteja dentro dos limites de entrada
    return ((x - input_min) / (input_max - input_min)) * (output_max - output_min) + output_min


def create_png_from_each_tiff(output_path):
    """Cria um PNG para cada imagem TIFF baixada."""
    files = [os.path.join(output_path, f) for f in os.listdir(output_path) if f.endswith(".tif")]
    if not files:
        raise FileNotFoundError("Nenhum arquivo TIFF encontrado para gerar PNGs.")

    for file in tqdm(files, desc="Convertendo imagens TIFF para PNG"):
        with rasterio.open(file) as src:
            img_array = src.read([1, 2, 3])  # Lê as bandas RGB (Bandas 1, 2, 3)
            img_array = img_array.astype(np.float32)  # Converte para float para aplicar a normalização

            # Define os limites de entrada para normalização com base nos percentis para melhorar contraste
            input_min = np.percentile(img_array, 2)  # Percentil 2 para evitar valores extremos
            input_max = np.percentile(img_array, 98)  # Percentil 98 para evitar valores extremos

            # Normaliza as bandas usando a função de escala linear
            img_array = linear_scale_range(img_array, input_min, input_max, 0, 255).astype(np.uint8)

            rgb_image = Image.fromarray(np.transpose(img_array, (1, 2, 0)))
            png_filename = os.path.splitext(os.path.basename(file))[0] + ".png"
            rgb_image.save(os.path.join(output_path, png_filename))
            logger.info(f"Imagem PNG salva como {png_filename}")


def get_user_inputs():
    """Solicita as entradas do usuário através de caixas de diálogo."""
    root = Tk()
    root.withdraw()

    directory = filedialog.askdirectory(title="Selecione o diretório do shapefile da área de interesse")
    if not directory:
        messagebox.showerror("Erro", "Nenhum diretório selecionado para o shapefile.")
        return None, None, None, None

    output_dir = filedialog.askdirectory(title="Selecione o diretório para salvar os resultados")
    if not output_dir:
        messagebox.showerror("Erro", "Nenhum diretório selecionado para salvar os resultados.")
        return None, None, None, None

    start_date = simpledialog.askstring("Data de Início", "Insira a data de início (YYYY-MM-DD):")
    if not start_date:
        messagebox.showerror("Erro", "Data de início não fornecida.")
        return None, None, None, None

    end_date = simpledialog.askstring("Data de Término", "Insira a data de término (YYYY-MM-DD):")
    if not end_date:
        messagebox.showerror("Erro", "Data de término não fornecida.")
        return None, None, None, None

    return directory, output_dir, start_date, end_date


def main():
    """Função principal que coordena o fluxo de trabalho."""
    directory, output_dir, start_date, end_date = get_user_inputs()
    if not all([directory, output_dir, start_date, end_date]):
        return

    url = "https://openeo.dataspace.copernicus.eu"
    try:
        connection = connect_and_authenticate(url)
        shapefile_path = find_shapefile_in_directory(directory)
        fields = define_fields(shapefile_path)
        spatial_extent = get_bounding_box(fields)

        # Carrega e processa o cubo de dados para extrair RGB
        cube_s2_rgb = load_rgb_data(connection, spatial_extent, start_date, end_date)
        job = process_data_cube(cube_s2_rgb)

        # Baixa os resultados da série
        download_results(job, output_dir)

        # Renomeia os arquivos baixados com datas correspondentes
        rename_files_with_metadata(output_dir)

        # Cria um PNG para cada imagem da série temporal
        create_png_from_each_tiff(output_dir)

        messagebox.showinfo("Sucesso", "O processo foi concluído com sucesso e os resultados foram salvos.")

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        messagebox.showerror("Erro", f"Erro no processamento: {e}")


if __name__ == '__main__':
    main()
