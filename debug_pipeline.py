import json
import logging
import pandas as pd
import geopandas as gpd
from pathlib import Path
from geoprocessing import load_kml, save_kml, fill_holes, generate_points_along_lines

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('debug_pipeline')

# Load configuration
try:
    with open('debug_config.json', 'r') as f:
        config = json.load(f)
except Exception as e:
    logger.error(f"Failed to load debug_config.json: {e}")
    config = {
        "point_distance": 0.003,
        "morph_buffer": 0.0001,
        "ap_area_threshold": 1e-05,
        "sm_area_threshold": 1e-05
    }

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_debug_kml(gdf, filename):
    if not gdf.empty:
        logger.info(f"Saving debug file: {filename} (features: {len(gdf)})")
        save_kml(gdf, DATA_DIR / filename)


def run_debug_ap_model(old_ap_gdf, new_ap_gdf, ukr_prov_gdf=None):
    logger.info("--- Starting Debug AP Model ---")

    if ukr_prov_gdf is None or ukr_prov_gdf.empty:
        ukr_prov_lines = gpd.GeoDataFrame(geometry=[])
    else:
        ukr_country = ukr_prov_gdf.dissolve()
        ukr_prov_lines = ukr_country.copy()
        ukr_prov_lines.geometry = ukr_prov_lines.geometry.boundary

    # Identify Russian layer
    if 'LayerName' in new_ap_gdf.columns and any(new_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)):
        new_ru_polys = new_ap_gdf[new_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)].copy()
    else:
        new_ru_polys = new_ap_gdf.copy()

    save_debug_kml(new_ru_polys, 'ap_step1_new_ru_polys.kml')

    if 'LayerName' in old_ap_gdf.columns and any(old_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)):
        old_ru_polys = old_ap_gdf[old_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)].copy()
    else:
        old_ru_polys = None

    if old_ru_polys is not None:
        save_debug_kml(old_ru_polys, 'ap_step2_old_ru_polys.kml')

    new_ru_polys = new_ru_polys[new_ru_polys.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_ru_dissolved = new_ru_polys.dissolve()
    new_ru_dissolved.geometry = new_ru_dissolved.geometry.apply(fill_holes)
    save_debug_kml(new_ru_dissolved, 'ap_step3_new_ru_dissolved.kml')

    # Create new Ukrainians map
    if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
        ukr_dissolved = ukr_prov_gdf.dissolve()
        ukr_dissolved.geometry = ukr_dissolved.geometry.apply(fill_holes)
        if not new_ru_dissolved.empty:
            new_ukr_dissolved = gpd.overlay(ukr_dissolved, new_ru_dissolved, how='difference')
        else:
            new_ukr_dissolved = ukr_dissolved.copy()
    else:
        new_ukr_dissolved = new_ru_dissolved.copy()

    if not new_ukr_dissolved.empty:
        new_ukr_dissolved = new_ukr_dissolved[new_ukr_dissolved.geometry.area > 1e-2]

    save_debug_kml(new_ukr_dissolved, 'ap_step4_new_ukr_dissolved.kml')

    # Create old Ukrainians map
    if old_ru_polys is not None:
        old_ru_polys = old_ru_polys[old_ru_polys.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        old_ru_dissolved = old_ru_polys.dissolve()
        old_ru_dissolved.geometry = old_ru_dissolved.geometry.apply(fill_holes)
        if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
            old_ukr_dissolved = gpd.overlay(ukr_dissolved, old_ru_dissolved, how='difference')
        else:
            old_ukr_dissolved = old_ru_dissolved.copy()
    else:
        old_ap_polys = old_ap_gdf[old_ap_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])].copy()
        old_ukr_dissolved = old_ap_polys.dissolve()
        old_ukr_dissolved.geometry = old_ukr_dissolved.geometry.apply(fill_holes)

    if not old_ukr_dissolved.empty:
        old_ukr_dissolved = old_ukr_dissolved[old_ukr_dissolved.geometry.area > 1e-2]

    save_debug_kml(old_ukr_dissolved, 'ap_step5_old_ukr_dissolved.kml')

    # Apply Morphological Closing
    mb = config.get("morph_buffer", 0.0001)
    if not new_ukr_dissolved.empty:
        new_ukr_dissolved.geometry = new_ukr_dissolved.buffer(mb).buffer(-mb)
    if not old_ukr_dissolved.empty:
        old_ukr_dissolved.geometry = old_ukr_dissolved.buffer(mb).buffer(-mb)

    save_debug_kml(new_ukr_dissolved, 'ap_step6_new_ukr_morph.kml')
    save_debug_kml(old_ukr_dissolved, 'ap_step7_old_ukr_morph.kml')

    old_buffered = old_ukr_dissolved.copy()
    old_buffered.geometry = old_buffered.buffer(0.0002)

    new_buffered = new_ukr_dissolved.copy()
    new_buffered.geometry = new_buffered.buffer(0.0002)

    # Difference: new - old = Ukrainian Gains
    if not new_ukr_dissolved.empty and not old_ukr_dissolved.empty:
        ukr_gains_area = gpd.overlay(new_ukr_dissolved, old_ukr_dissolved, how='difference')
    elif not new_ukr_dissolved.empty:
        ukr_gains_area = new_ukr_dissolved.copy()
    else:
        ukr_gains_area = gpd.GeoDataFrame(geometry=[])

    # Difference: old - new = Russian Gains (Ukrainian losses)
    if not old_ukr_dissolved.empty and not new_ukr_dissolved.empty:
        ru_gains_area = gpd.overlay(old_ukr_dissolved, new_ukr_dissolved, how='difference')
    elif not old_ukr_dissolved.empty:
        ru_gains_area = old_ukr_dissolved.copy()
    else:
        ru_gains_area = gpd.GeoDataFrame(geometry=[])

    save_debug_kml(ukr_gains_area, 'ap_step8_ukr_gains_area_raw.kml')
    save_debug_kml(ru_gains_area, 'ap_step9_ru_gains_area_raw.kml')

    # Filter by area threshold
    area_thresh = config.get("ap_area_threshold", 1e-5)
    if not ukr_gains_area.empty:
        ukr_gains_area = ukr_gains_area[ukr_gains_area.geometry.area > area_thresh]
    if not ru_gains_area.empty:
        ru_gains_area = ru_gains_area[ru_gains_area.geometry.area > area_thresh]

    save_debug_kml(ukr_gains_area, 'ap_step10_ukr_gains_area_filtered.kml')
    save_debug_kml(ru_gains_area, 'ap_step11_ru_gains_area_filtered.kml')

    if not ukr_gains_area.empty:
        ukr_boundaries = ukr_gains_area.copy()
        ukr_boundaries.geometry = ukr_boundaries.geometry.boundary
    else:
        ukr_boundaries = gpd.GeoDataFrame(geometry=[])

    if not ru_gains_area.empty:
        ru_boundaries = ru_gains_area.copy()
        ru_boundaries.geometry = ru_boundaries.geometry.boundary
    else:
        ru_boundaries = gpd.GeoDataFrame(geometry=[])

    pd_dist = config.get("point_distance", 0.003)
    points_ukr = generate_points_along_lines(ukr_boundaries, pd_dist)
    points_ru = generate_points_along_lines(ru_boundaries, pd_dist)

    # Erase country borders
    if not ukr_prov_lines.empty:
        ukr_prov_buffer = ukr_prov_lines.copy()
        ukr_prov_buffer.geometry = ukr_prov_buffer.buffer(0.01)
        if not points_ukr.empty:
            points_ukr = gpd.overlay(points_ukr, ukr_prov_buffer, how='difference')
        if not points_ru.empty:
            points_ru = gpd.overlay(points_ru, ukr_prov_buffer, how='difference')

    if not points_ukr.empty and not old_buffered.empty:
        points_ukr = gpd.sjoin(points_ukr, old_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ukr.columns:
            points_ukr = points_ukr.drop(columns=['index_right'])

    if not points_ru.empty and not new_buffered.empty:
        points_ru = gpd.overlay(points_ru, new_buffered, how='difference')

    if not points_ukr.empty:
        points_ukr['Name'] = 'Ukr gains'
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs if not points_ukr.empty else None)

    if not points_ru.empty:
        points_ru['Name'] = 'Ru gains'
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ru.crs if not points_ru.empty else None)

    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs)

    save_debug_kml(pins_out, 'ap_step12_final_pins.kml')

    map_out = new_ukr_dissolved.copy()
    map_out = map_out[['geometry']]
    map_out['Name'] = 'Ukrainians'

    save_debug_kml(map_out, 'ap_step13_final_map.kml')

    logger.info("--- Finished Debug AP Model ---")
    return map_out, pins_out


def run_debug_sm_model(old_sm_gdf, new_sm_gdf, ukr_prov_gdf=None):
    logger.info("--- Starting Debug SM Model ---")

    old_sm_gdf['Name'] = old_sm_gdf['Name'].fillna('')
    new_sm_gdf['Name'] = new_sm_gdf['Name'].fillna('')

    old_sm = old_sm_gdf[~old_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()
    new_sm = new_sm_gdf[~new_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()

    old_sm = old_sm[old_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_sm = new_sm[new_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
        ukr_prov_gdf['Name'] = ukr_prov_gdf['Name'].fillna('')
        crimea = ukr_prov_gdf[ukr_prov_gdf['Name'].str.contains('Crimea', case=False, na=False)].copy()

        ukr_country = ukr_prov_gdf.dissolve()
        ukr_prov_lines = ukr_country.copy()
        ukr_prov_lines.geometry = ukr_prov_lines.geometry.boundary
    else:
        crimea = gpd.GeoDataFrame(geometry=[])
        ukr_prov_lines = gpd.GeoDataFrame(geometry=[])

    old_dissolved = old_sm.dissolve()
    old_dissolved.geometry = old_dissolved.geometry.apply(fill_holes)
    save_debug_kml(old_dissolved, 'sm_step1_old_dissolved.kml')

    new_dissolved = new_sm.dissolve()
    new_dissolved.geometry = new_dissolved.geometry.apply(fill_holes)
    save_debug_kml(new_dissolved, 'sm_step2_new_dissolved.kml')

    # Morphological Closing
    mb = config.get("morph_buffer", 0.0001)
    if not old_dissolved.empty:
        old_dissolved.geometry = old_dissolved.buffer(mb).buffer(-mb)
    if not new_dissolved.empty:
        new_dissolved.geometry = new_dissolved.buffer(mb).buffer(-mb)

    save_debug_kml(old_dissolved, 'sm_step3_old_morph.kml')
    save_debug_kml(new_dissolved, 'sm_step4_new_morph.kml')

    old_buffered = old_dissolved.copy()
    old_buffered.geometry = old_buffered.buffer(0.0002)
    old_buffered = old_buffered.dissolve()

    new_buffered = new_dissolved.copy()
    new_buffered.geometry = new_buffered.buffer(0.0002)
    new_buffered = new_buffered.dissolve()

    if not new_dissolved.empty and not old_dissolved.empty:
        new_line_area = gpd.overlay(new_dissolved, old_dissolved, how='difference')
    elif not new_dissolved.empty:
        new_line_area = new_dissolved.copy()
    else:
        new_line_area = gpd.GeoDataFrame(geometry=[])

    if not old_dissolved.empty and not new_dissolved.empty:
        old_line_area = gpd.overlay(old_dissolved, new_dissolved, how='difference')
    elif not old_dissolved.empty:
        old_line_area = old_dissolved.copy()
    else:
        old_line_area = gpd.GeoDataFrame(geometry=[])

    save_debug_kml(new_line_area, 'sm_step5_new_line_area_raw.kml')
    save_debug_kml(old_line_area, 'sm_step6_old_line_area_raw.kml')

    if not crimea.empty:
        if not new_line_area.empty:
            new_line_area = gpd.overlay(new_line_area, crimea, how='difference')
        if not old_line_area.empty:
            old_line_area = gpd.overlay(old_line_area, crimea, how='difference')

    area_thresh = config.get("sm_area_threshold", 1e-5)
    if not new_line_area.empty:
        new_line_area = new_line_area[new_line_area.geometry.area > area_thresh]
    if not old_line_area.empty:
        old_line_area = old_line_area[old_line_area.geometry.area > area_thresh]

    save_debug_kml(new_line_area, 'sm_step7_new_line_area_filtered.kml')
    save_debug_kml(old_line_area, 'sm_step8_old_line_area_filtered.kml')

    if not old_line_area.empty:
        old_boundaries = old_line_area.copy()
        old_boundaries.geometry = old_boundaries.geometry.boundary
    else:
        old_boundaries = gpd.GeoDataFrame(geometry=[])

    if not new_line_area.empty:
        new_boundaries = new_line_area.copy()
        new_boundaries.geometry = new_boundaries.geometry.boundary
    else:
        new_boundaries = gpd.GeoDataFrame(geometry=[])

    pd_dist = config.get("point_distance", 0.003)
    points_ukr = generate_points_along_lines(old_boundaries, pd_dist)
    points_ru = generate_points_along_lines(new_boundaries, pd_dist)

    if not ukr_prov_lines.empty:
        ukr_prov_buffer = ukr_prov_lines.copy()
        ukr_prov_buffer.geometry = ukr_prov_buffer.buffer(0.01)
        if not points_ukr.empty:
            points_ukr = gpd.overlay(points_ukr, ukr_prov_buffer, how='difference')
        if not points_ru.empty:
            points_ru = gpd.overlay(points_ru, ukr_prov_buffer, how='difference')

    if not points_ukr.empty and not new_buffered.empty:
        points_ukr = gpd.overlay(points_ukr, new_buffered, how='difference')

    if not points_ru.empty and not old_buffered.empty:
        points_ru = gpd.sjoin(points_ru, old_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ru.columns:
            points_ru = points_ru.drop(columns=['index_right'])

    if not points_ukr.empty:
        points_ukr['Name'] = 'Ukr gains'
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs if not points_ukr.empty else None)

    if not points_ru.empty:
        points_ru['Name'] = 'Ru gains'
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ru.crs if not points_ru.empty else None)

    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs)

    save_debug_kml(pins_out, 'sm_step9_final_pins.kml')

    map_out = new_sm.copy()
    if not crimea.empty:
        crimea_cleaned = crimea[['geometry']].copy()
        crimea_cleaned['Name'] = 'Autonomous Republic of Crimea'
        map_out = pd.concat([map_out, crimea_cleaned], ignore_index=True)
        map_out = gpd.GeoDataFrame(map_out, geometry='geometry')

    if 'Name' not in map_out.columns:
        map_out['Name'] = ''

    save_debug_kml(map_out, 'sm_step10_final_map.kml')

    logger.info("--- Finished Debug SM Model ---")
    return map_out, pins_out


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Run geoprocessing models step-by-step for debugging.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Example Usage (Inside Docker):
  python debug_pipeline.py --ap-old "/app/data/AP Base.kml" --ap-new "/app/data/AP Update.kml"
  python debug_pipeline.py --sm-old "/app/data/SM Base.kml" --sm-new "/app/data/SM Update.kml"

You can run both models at the same time by providing all four arguments.
Make sure your files are located in the /app/data directory.
"""
    )

    parser.add_argument("--ap-old", type=str, help="Path to the Old/Base AP Map KML file")
    parser.add_argument("--ap-new", type=str, help="Path to the New AP Map KML file")
    parser.add_argument("--sm-old", type=str, help="Path to the Old/Base SM Map KML file")
    parser.add_argument("--sm-new", type=str, help="Path to the New SM Map KML file")
    parser.add_argument("--ukr-prov", type=str, default="/app/data/ukraine-with-regions_1530.kml", help="Path to Ukraine Provinces boundary file")

    args = parser.parse_args()

    if not (args.ap_old and args.ap_new) and not (args.sm_old and args.sm_new):
        parser.print_help()
        logger.error("\nYou must provide both Old and New files for at least one model (AP or SM).")
        sys.exit(1)

    ukr_prov_gdf = None
    if Path(args.ukr_prov).exists():
        logger.info(f"Loading Ukraine Provinces boundary from {args.ukr_prov}")
        ukr_prov_gdf = load_kml(args.ukr_prov)
    else:
        logger.warning(f"Ukraine Provinces boundary not found at {args.ukr_prov}. Proceeding without country border clipping.")

    if args.ap_old and args.ap_new:
        logger.info(f"Loading AP Old: {args.ap_old}")
        ap_old_gdf = load_kml(args.ap_old)
        logger.info(f"Loading AP New: {args.ap_new}")
        ap_new_gdf = load_kml(args.ap_new)

        if ap_old_gdf.empty or ap_new_gdf.empty:
            logger.error("Failed to load one or both AP maps. Check the file paths.")
        else:
            run_debug_ap_model(ap_old_gdf, ap_new_gdf, ukr_prov_gdf)

    if args.sm_old and args.sm_new:
        logger.info(f"Loading SM Old: {args.sm_old}")
        sm_old_gdf = load_kml(args.sm_old)
        logger.info(f"Loading SM New: {args.sm_new}")
        sm_new_gdf = load_kml(args.sm_new)

        if sm_old_gdf.empty or sm_new_gdf.empty:
            logger.error("Failed to load one or both SM maps. Check the file paths.")
        else:
            run_debug_sm_model(sm_old_gdf, sm_new_gdf, ukr_prov_gdf)

    logger.info("Debug pipeline execution completed.")
