#!/usr/local/share/conda_envs/tesspatrol_conda/bin/python

from astropy.io import fits
from astropy.wcs import WCS
from glob import glob
import sqlalchemy
import logging
import yaml
import sys
import os


# Main project
PROJECT_DIR = "/data/projects/TESS"
SCRIPT_DIR = PROJECT_DIR + "/subtaction_code/scripts/"
CONFIG_DIR = PROJECT_DIR + "/subtaction_code/aux/"
DATA_DIR = PROJECT_DIR + "/data/"
LOG_DIR = PROJECT_DIR + "/log/"

# Get sector dir from args
payload_dir = os.path.abspath(sys.argv[1])
contents = os.listdir(payload_dir)
sector_data_dir = DATA_DIR + payload_dir.split("/")[-1]
sector_id = int(payload_dir.split("/")[-1][-4:])

# Set logger
logger = logging.getLogger("ingest-sector")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

log_file = LOG_DIR + f"ingest_sector_{sector_id:04d}.log"
handler = logging.FileHandler(log_file)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Read config
with open(CONFIG_DIR + "tess_pipeline.yaml") as stream:
    config = yaml.safe_load(stream)

# Connect to database
logger.info("connecting to database")
url_object = sqlalchemy.URL.create(
    "postgresql+psycopg2",
    username=config['db_user'],
    password=config['db_pass'],
    database=config['db_name'],
    host=config['db_host'])
engine = sqlalchemy.create_engine(url_object)

# Update field info to database
logger.info("logging images to database")
mjd_beg = 999999
mjd_end = 0
for i in [1, 2, 3, 4]:
    for j in [1, 2, 3, 4]:
        cam_ccd_dir = sector_data_dir + f"/cam{i}-ccd{j}/"
        cam_ccd_imgs = [os.path.basename(fits) for fits in glob(cam_ccd_dir + "hlsp_*.fits")]

        # Read single img for field data
        with fits.open(cam_ccd_dir + "ref.wcs") as hdul:
            img = hdul[0]
            wcs_str = WCS(img.header).to_header_string(relax=True)
            # Escape single quotes for entry into DB
            wcs_str = wcs_str.replace("'", "''")

        # First transaction for field
        with engine.begin() as conn:
            statement = f"INSERT INTO fields " \
                        f"(sector_id, camera_id, ccd_id) " \
                        f"VALUES " \
                        f"({sector_id}, {i}, {j}]"
            conn.execute(sqlalchemy.text(statement))
            # Field ID needed for image table
            statement = f"SELECT field_id FROM fields " \
                        f"WHERE sector_id = {sector_id} AND camera_id = {i} AND ccd_id = {j}"
            field_id = conn.execute(sqlalchemy.text(statement)).first()[0]

        # Second transaction for images
        with engine.begin() as conn:
            for img_file in cam_ccd_imgs:
                with fits.open(cam_ccd_dir + img) as hdul:
                    hdr = hdul[0].header
                    exp_time = hdr["EXPTIME"]
                    cadence = hdr['CADENCE']
                    mjd_beg = hdr["MJD-BEG"]
                    mjd_end = hdr["MJD-END"]
                    mjd_mid = (mjd_beg + mjd_end) / 2
                # Submit
                statement = f"INSERT INTO images " \
                            f"(cadence, field_id, filename, mjd_beg, mjd_mid, mjd_end, exp_time) " \
                            f"VALUES " \
                            f"({cadence}, {field_id}, '{img_file}', {mjd_beg}, {mjd_mid}, {mjd_end}, {exp_time})"
                conn.execute(sqlalchemy.text(statement))

                # MJD Bounds for sector
                sec_mjd_beg = min(mjd_beg, img.header["MJD-BEG"])
                sec_mjd_end = max(mjd_end, img.header["MJD-END"])

# Log sector in postgres
logger.info("finishing database logging")
with engine.begin() as conn:
    statatement = f"INSERT INTO sectors " \
                  f"(sector_id, mjd_start, mjd_finish) " \
                  f"VALUES " \
                  f"({sector_id}, {sec_mjd_beg}, {sec_mjd_end})"
    conn.execute(sqlalchemy.text(statement))