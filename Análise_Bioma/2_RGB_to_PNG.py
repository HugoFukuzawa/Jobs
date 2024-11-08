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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("log")

def clr_tkn():
    logger.info("Limpando tokens...")
    RefreshTokenStore().remove()
    logger.info("Tokens limpos.")

def cnct_at(url):
    try:
        conn = openeo.connect(url=url)
        conn.authenticate_oidc()
        logger.info(f"Conectado ao openEO em: {url}")
        return conn
    except openeo.rest.auth.AuthException:
        logger.warning("Erro de autenticação. Limpando token...")
        clr_tkn()
        conn = openeo.connect(url=url)
        conn.authenticate_oidc()
        return conn
    except Exception as e:
        logger.error(f"Erro na conexão: {e}")
        raise

def shp_dir(d):
    for f in os.listdir(d):
        if f.endswith(".shp"):
            return os.path.join(d, f)
    raise FileNotFoundError(f"Sem shapefile em: {d}")

def rpj_shp(s):
    return gpd.read_file(s).to_crs("EPSG:4326")

def get_bbox(df):
    b = df.total_bounds
    return {"west": b[0], "south": b[1], "east": b[2], "north": b[3]}

def load_rgb(conn, extent, sd, ed, cloud=15):
    return conn.load_collection(
        "SENTINEL2_L2A", spatial_extent=extent, temporal_extent=[sd, ed], bands=["B04", "B03", "B02"], max_cloud_cover=cloud
    )

def prc_data(cube):
    res = cube.save_result(format="GTIFF", options={"output_band": "RGB"})
    job = res.create_job(title="rgb_ts")
    job.start_and_wait()
    if job.status() != "finished":
        logger.error(f"Erro no job: {job.status()}")
        raise ValueError(f"Job com erro: {job.job_id}")
    return job

def dwnld(job, out_path):
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    job.get_results().download_files(target=out_path)

def ren_files(out_path):
    files = [f for f in os.listdir(out_path) if f.endswith(".tif")]
    for f in files:
        with rasterio.open(os.path.join(out_path, f)) as ds:
            try:
                dt = ds.tags().get('TIFFTAG_DATETIME')
                if dt:
                    new_name = f"RGB_{datetime.strptime(dt, '%Y:%m:%d %H:%M:%S').strftime('%Y-%m-%d')}.tif"
                    os.rename(os.path.join(out_path, f), os.path.join(out_path, new_name))
                    logger.info(f"Arquivo renomeado para {new_name}")
            except Exception as e:
                logger.warning(f"Erro ao renomear: {e}")

def scale_range(x, i_min, i_max, o_min=0, o_max=255):
    x = np.clip(x, i_min, i_max)
    return ((x - i_min) / (i_max - i_min)) * (o_max - o_min) + o_min

def tiff_to_png(out_path):
    files = [os.path.join(out_path, f) for f in os.listdir(out_path) if f.endswith(".tif")]
    if not files:
        raise FileNotFoundError("Nenhum TIFF para PNG.")
    for f in tqdm(files, desc="Convertendo TIFF para PNG"):
        with rasterio.open(f) as src:
            arr = src.read([1, 2, 3]).astype(np.float32)
            i_min, i_max = np.percentile(arr, 2), np.percentile(arr, 98)
            arr = scale_range(arr, i_min, i_max, 0, 255).astype(np.uint8)
            Image.fromarray(np.transpose(arr, (1, 2, 0))).save(os.path.join(out_path, f"{os.path.splitext(os.path.basename(f))[0]}.png"))
            logger.info(f"PNG salvo como {os.path.splitext(os.path.basename(f))[0]}.png")

def usr_inputs():
    root = Tk()
    root.withdraw()
    dir = filedialog.askdirectory(title="Selecionar diretório shapefile")
    if not dir:
        return None, None, None, None
    out = filedialog.askdirectory(title="Selecionar diretório de saída")
    if not out:
        return None, None, None, None
    sd = simpledialog.askstring("Data Início", "AAAA-MM-DD:")
    if not sd:
        return None, None, None, None
    ed = simpledialog.askstring("Data Fim", "AAAA-MM-DD:")
    if not ed:
        return None, None, None, None
    return dir, out, sd, ed

def run():
    dir, out, sd, ed = usr_inputs()
    if not all([dir, out, sd, ed]):
        return
    try:
        conn = cnct_at("https://openeo.dataspace.copernicus.eu")
        shp = shp_dir(dir)
        fields = rpj_shp(shp)
        bbox = get_bbox(fields)
        rgb = load_rgb(conn, bbox, sd, ed)
        job = prc_data(rgb)
        dwnld(job, out)
        ren_files(out)
        tiff_to_png(out)
        messagebox.showinfo("Sucesso", "Processo concluído.")
    except Exception as e:
        logger.error(f"Erro: {e}")
        messagebox.showerror("Erro", f"Erro: {e}")

if __name__ == '__main__':
    run()
