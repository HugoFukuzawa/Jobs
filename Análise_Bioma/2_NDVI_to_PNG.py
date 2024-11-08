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
from pyproj import Transformer

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

def load_ndvi(conn, extent, sd, ed):
    try:
        cube = conn.load_collection("SENTINEL2_L2A", spatial_extent=extent, temporal_extent=[sd, ed], bands=["B08", "B04"], max_cloud_cover=15)
        if cube is None:
            logger.error("Erro ao carregar coleção.")
            raise ValueError("Coleção vazia.")
        return cube.apply(lambda x: (x["B08"] - x["B04"]) / (x["B08"] + x["B04"]))
    except Exception as e:
        logger.error(f"Erro ao carregar NDVI: {e}")
        raise

def prc_data(cube):
    try:
        res = cube.save_result(format="GTIFF", options={"output_band": "NDVI"})
        job = res.create_job(title="ndvi_ts")
        job.start_and_wait()
        if job.status() != "finished":
            logger.error(f"Erro no job: {job.status()}")
            raise ValueError(f"Job com erro: {job.job_id}")
        return job
    except Exception as e:
        logger.error(f"Erro no processamento do job: {e}")
        raise

def dwnld(job, out_path):
    try:
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        job.get_results().download_files(target=out_path)
    except Exception as e:
        logger.error(f"Erro ao baixar resultados: {e}")
        raise

def tiff_to_png(tiff_p, png_p):
    try:
        cmap = plt.get_cmap('RdYlGn')
        with rasterio.open(tiff_p) as src:
            arr = src.read(1)
            if arr is None or arr.size == 0:
                logger.error(f"TIFF vazio: {tiff_p}")
                raise ValueError("Sem dados NDVI.")
            arr_norm = (arr - (-1)) / (1 - (-1))
            arr_norm = np.clip(arr_norm, 0, 1)
            arr_norm = np.ma.masked_where((arr < -1) | (arr > 1), arr_norm)
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.imshow(arr_norm, cmap=cmap, vmin=0, vmax=1, interpolation='none')
            plt.savefig(png_p, format='png', dpi=300, bbox_inches='tight')
            plt.close()
    except Exception as e:
        logger.error(f"Erro ao converter TIFF para PNG: {e}")

def prc_all_tiffs(in_dir, out_dir):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    for f in os.listdir(in_dir):
        if f.lower().endswith('.tif'):
            tiff_to_png(os.path.join(in_dir, f), os.path.join(out_dir, f"{os.path.splitext(f)[0]}.png"))

def run():
    root = Tk()
    root.withdraw()
    dir = filedialog.askdirectory(title="Selecionar diretório shapefile")
    if not dir:
        return
    out = filedialog.askdirectory(title="Selecionar diretório de saída")
    if not out:
        return
    sd = simpledialog.askstring("Data Início", "AAAA-MM-DD:")
    if not sd:
        return
    ed = simpledialog.askstring("Data Fim", "AAAA-MM-DD:")
    if not ed:
        return
    try:
        conn = cnct_at("https://openeo.dataspace.copernicus.eu")
        shp = shp_dir(dir)
        fields = rpj_shp(shp)
        bbox = get_bbox(fields)
        ndvi = load_ndvi(conn, bbox, sd, ed)
        job = prc_data(ndvi)
        dwnld(job, out)
        prc_all_tiffs(out, out)
    except Exception as e:
        logger.error(f"Erro no fluxo: {e}")
        messagebox.showerror("Erro", f"Erro: {e}")

if __name__ == '__main__':
    run()
