import geopandas as gpd
import fiona
from shapely.geometry import Polygon, MultiPolygon, MultiLineString, LineString, Point
import shapely
from shapely.validation import make_valid
import warnings
import os
from bs4 import BeautifulSoup
import pyogrio
import pandas as pd

warnings.filterwarnings('ignore', message='.*KML.*')
warnings.filterwarnings('ignore', message='.*Self-intersection.*')

fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

def snap_to_grid(gdf, precision=1e-7):
    # The QGIS script uses round(x, 7). 1e-7 matches that precision exactly.
    if gdf.empty: return gdf
    gdf = gdf.copy()
    gdf.geometry = shapely.set_precision(gdf.geometry, grid_size=precision)
    return gdf

def load_kml(filepath):
    try:
        layers = pyogrio.list_layers(filepath)
        gdfs = []
        for layer_info in layers:
            layer_name = layer_info[0]
            try:
                gdf = gpd.read_file(filepath, layer=layer_name, driver='KML')
                if not gdf.empty:
                    gdf['LayerName'] = layer_name
                    gdfs.append(gdf)
            except:
                pass

        if not gdfs:
            return gpd.GeoDataFrame()

        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)

        if 'Name' in gdf.columns:
            gdf['Name'] = gdf['Name'].fillna('')
        else:
            gdf['Name'] = ''

        if not gdf.empty and 'geometry' in gdf.columns:
            gdf.geometry = gdf.geometry.apply(lambda geom: make_valid(geom) if geom is not None else geom)

        # Apply the explicit QGIS coordinate rounding (7 decimal places)
        # gdf = snap_to_grid(gdf, precision=1e-7)
        return gdf
    except Exception as e:
        print(f"Error loading KML {filepath}: {e}")
        return gpd.GeoDataFrame()

def save_kml(gdf, filepath, name_col='Name'):
    if gdf.empty:
        with open(filepath, 'w') as f:
            f.write('<?xml version="1.0" encoding="utf-8" ?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document id="root_doc">\n<Folder><name>empty</name></Folder>\n</Document>\n</kml>')
        return

    def force_3d_and_valid(geom):
        if geom is None or geom.is_empty:
            return geom
        geom = make_valid(geom)
        if geom.geom_type == 'GeometryCollection':
            parts = [p for p in geom.geoms if p.geom_type in ['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString', 'Point']]
            if parts:
                geom = parts[0]
        return shapely.force_3d(geom)

    gdf = gdf.copy()
    gdf.geometry = gdf.geometry.apply(force_3d_and_valid)
    gdf = gdf[~gdf.geometry.is_empty]

    if name_col != 'Name' and name_col in gdf.columns:
        gdf['Name'] = gdf[name_col]

    cols_to_keep = ['Name', 'geometry']
    if 'description' in gdf.columns:
        cols_to_keep.append('description')

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        gdf.to_file(filepath, driver="KML")
    except Exception as e:
        print(f"Error writing to KML, falling back to GeoJSON for debug: {e}")
        gdf.to_file(filepath + ".geojson", driver="GeoJSON")

def copy_kml_styles(source_kml_path, target_kml_path):
    try:
        with open(source_kml_path, 'r', encoding='utf-8') as f:
            # Revert to 'xml' because the container definitely has lxml globally installed now
            # And bs4 falls back gracefully
            source_soup = BeautifulSoup(f.read(), 'xml')

        with open(target_kml_path, 'r', encoding='utf-8') as f:
            target_soup = BeautifulSoup(f.read(), 'xml')

        styles = source_soup.find_all('Style')
        style_maps = source_soup.find_all('StyleMap')

        target_doc = target_soup.find('Document')
        if not target_doc:
            return

        for sm in reversed(style_maps):
            target_doc.insert(0, sm)
        for s in reversed(styles):
            target_doc.insert(0, s)

        with open(target_kml_path, 'w', encoding='utf-8') as f:
            f.write(str(target_soup))

    except Exception as e:
        print(f"Error copying styles from {source_kml_path} to {target_kml_path}: {e}")

def generate_points_along_lines(lines_gdf, distance=0.003):
    points = []
    if lines_gdf.empty:
        return gpd.GeoDataFrame(columns=['geometry'], crs=lines_gdf.crs)

    lines = lines_gdf.explode(index_parts=False)

    for idx, row in lines.iterrows():
        line = row.geometry
        if line is None or line.is_empty:
            continue
        if line.geom_type not in ['LineString', 'MultiLineString']:
            if line.geom_type in ['Polygon', 'MultiPolygon']:
                line = line.boundary
            else:
                continue

        length = line.length
        current_dist = 0
        while current_dist <= length:
            points.append(line.interpolate(current_dist))
            current_dist += distance

    points_gdf = gpd.GeoDataFrame(geometry=points, crs=lines_gdf.crs)
    return points_gdf

def fill_holes(geom):
    # This acts identically to native:deleteholes by extracting only exterior boundaries
    if geom is None: return geom
    if geom.type == 'Polygon':
        return Polygon(geom.exterior)
    elif geom.type == 'MultiPolygon':
        return MultiPolygon([Polygon(p.exterior) for p in geom.geoms])
    return geom


def run_ap_model(old_ap_gdf, new_ap_gdf, ukr_prov_gdf=None):
    if ukr_prov_gdf is None or ukr_prov_gdf.empty:
        ukr_prov_lines = gpd.GeoDataFrame(geometry=[])
        ukr_dissolved = gpd.GeoDataFrame(geometry=[])
    else:
        ukr_country = ukr_prov_gdf.dissolve()
        ukr_prov_lines = ukr_country.copy()
        ukr_prov_lines.geometry = ukr_prov_lines.geometry.boundary
        ukr_dissolved = ukr_country.copy()
        ukr_dissolved.geometry = ukr_dissolved.geometry.apply(fill_holes)

    # ---------------------------------------------------------
    # 1. PROCESS NEW MAP (Always contains Russians)
    # ---------------------------------------------------------
    if 'LayerName' in new_ap_gdf.columns and any(new_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)):
        new_ru_polys = new_ap_gdf[new_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)].copy()
    else:
        new_ru_polys = new_ap_gdf.copy()

    new_ru_polys = new_ru_polys[new_ru_polys.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_ru_dissolved = new_ru_polys.dissolve()
    new_ru_dissolved.geometry = new_ru_dissolved.geometry.apply(fill_holes)

    # Create New Ukrainians map
    if not ukr_dissolved.empty:
        if not new_ru_dissolved.empty:
            new_ukr_dissolved = gpd.overlay(ukr_dissolved, new_ru_dissolved, how='difference')
        else:
            new_ukr_dissolved = ukr_dissolved.copy()
    else:
        new_ukr_dissolved = new_ru_dissolved.copy()

    if not new_ukr_dissolved.empty:
        new_ukr_dissolved = new_ukr_dissolved.explode(index_parts=False)
        new_ukr_dissolved = new_ukr_dissolved[new_ukr_dissolved.geometry.area > 1]
    
    # SNAP to grid immediately so the international borders freeze mathematically
    new_ukr_dissolved = snap_to_grid(new_ukr_dissolved, precision=1e-7)

    # ---------------------------------------------------------
    # 2. PROCESS OLD MAP (Smart Parser: Is it Russians or Ukrainians?)
    # ---------------------------------------------------------
    is_old_ukraine = False
    if 'Name' in old_ap_gdf.columns and any(old_ap_gdf['Name'].str.contains('Ukrainian', case=False, na=False)):
        is_old_ukraine = True
    elif 'LayerName' in old_ap_gdf.columns and any(old_ap_gdf['LayerName'].str.contains('Ukrainian', case=False, na=False)):
        is_old_ukraine = True

    if is_old_ukraine:
        # User provided the previous output map (Apples to Apples)
        old_ukr_polys = old_ap_gdf[old_ap_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])].copy()
        old_ukr_dissolved = old_ukr_polys.dissolve()
        old_ukr_dissolved.geometry = old_ukr_dissolved.geometry.apply(fill_holes)
    else:
        # User provided a raw map with Russians (Convert to Ukrainians)
        if 'LayerName' in old_ap_gdf.columns and any(old_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)):
            old_ru_polys = old_ap_gdf[old_ap_gdf['LayerName'].str.contains('Russian', case=False, na=False)].copy()
        else:
            old_ru_polys = old_ap_gdf.copy()
        
        old_ru_polys = old_ru_polys[old_ru_polys.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        old_ru_dissolved = old_ru_polys.dissolve()
        old_ru_dissolved.geometry = old_ru_dissolved.geometry.apply(fill_holes)

        if not ukr_dissolved.empty:
            if not old_ru_dissolved.empty:
                old_ukr_dissolved = gpd.overlay(ukr_dissolved, old_ru_dissolved, how='difference')
            else:
                old_ukr_dissolved = ukr_dissolved.copy()
        else:
            old_ukr_dissolved = old_ru_dissolved.copy()
        
        if not old_ukr_dissolved.empty:
            old_ukr_dissolved = old_ukr_dissolved.explode(index_parts=False)
            old_ukr_dissolved = old_ukr_dissolved[old_ukr_dissolved.geometry.area > 1]

    # SNAP to grid immediately to ensure the old borders match the new borders perfectly
    old_ukr_dissolved = snap_to_grid(old_ukr_dissolved, precision=1e-7)

    # ---------------------------------------------------------
    # 3. CALCULATE GAINS (Using matched Ukraine maps)
    # ---------------------------------------------------------
    if not new_ukr_dissolved.empty and not old_ukr_dissolved.empty:
        ukr_gains_area = gpd.overlay(new_ukr_dissolved, old_ukr_dissolved, how='difference')
        ru_gains_area = gpd.overlay(old_ukr_dissolved, new_ukr_dissolved, how='difference')
    else:
        ukr_gains_area = gpd.GeoDataFrame(geometry=[])
        ru_gains_area = gpd.GeoDataFrame(geometry=[])

    # Filter by area threshold to remove micro-slivers
    area_thresh = 1e-5
    if not ukr_gains_area.empty:
        ukr_gains_area = ukr_gains_area[ukr_gains_area.geometry.area > area_thresh]
    if not ru_gains_area.empty:
        ru_gains_area = ru_gains_area[ru_gains_area.geometry.area > area_thresh]

    # Extract Boundaries
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

    # Generate Points
    points_ukr = generate_points_along_lines(ukr_boundaries, 0.003)
    points_ru = generate_points_along_lines(ru_boundaries, 0.003)

    # ---------------------------------------------------------
    # 4. FILTER PINS TO TRACE THE *PREVIOUS* LINE
    # ---------------------------------------------------------
    old_ukr_buffered = old_ukr_dissolved.copy()
    if not old_ukr_buffered.empty:
        old_ukr_buffered.geometry = old_ukr_buffered.buffer(0.0002)

    new_ukr_buffered = new_ukr_dissolved.copy()
    if not new_ukr_buffered.empty:
        new_ukr_buffered.geometry = new_ukr_buffered.buffer(0.0002)

    # Ukr Gains (Russia retreated): Keep ONLY pins touching the OLD Ukraine frontline
    if not points_ukr.empty and not old_ukr_buffered.empty:
        points_ukr = gpd.sjoin(points_ukr, old_ukr_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ukr.columns:
            points_ukr = points_ukr.drop(columns=['index_right'])

    # Ru Gains (Russia advanced): Remove pins touching the NEW Ukraine frontline
    if not points_ru.empty and not new_ukr_buffered.empty:
        points_ru = gpd.overlay(points_ru, new_ukr_buffered, how='difference')

    # Label Pins
    if not points_ukr.empty:
        points_ukr['Name'] = 'Ukr gains'
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs if not points_ukr.empty else None)

    if not points_ru.empty:
        points_ru['Name'] = 'Ru gains'
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ru.crs if not points_ru.empty else None)

    # Compile Pins Output
    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs)

    # Compile Map Output
    map_out = new_ukr_dissolved.copy()
    map_out = map_out[['geometry']]
    map_out['Name'] = 'Ukrainians'
    
    return map_out, pins_out

def run_sm_model(old_sm_gdf, new_sm_gdf, ukr_prov_gdf=None):
    old_sm_gdf['Name'] = old_sm_gdf['Name'].fillna('')
    new_sm_gdf['Name'] = new_sm_gdf['Name'].fillna('')

    old_sm = old_sm_gdf[~old_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()
    new_sm = new_sm_gdf[~new_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()

    old_sm = old_sm[~old_sm['Name'].str.contains('Crimea', case=False, na=False)]
    new_sm = new_sm[~new_sm['Name'].str.contains('Crimea', case=False, na=False)]
    
    old_sm = old_sm[old_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_sm = new_sm[new_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    # --- THE FIX: Pre-Snapping ---
    # Snap the raw polygons to the grid immediately. This forces adjacent internal borders 
    # to perfectly align before they melt, eliminating artifacts without rounding the outer corners!
    old_sm = snap_to_grid(old_sm, precision=1e-7)
    new_sm = snap_to_grid(new_sm, precision=1e-7)

    # Process Crimea template for final output
    if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
        ukr_prov_gdf['Name'] = ukr_prov_gdf['Name'].fillna('')
        crimea_mask = ukr_prov_gdf['Name'].str.contains('Crimea', case=False, na=False) | ukr_prov_gdf['Name'].isin(['01', '85'])
        if 'description' in ukr_prov_gdf.columns:
            ukr_prov_gdf['description'] = ukr_prov_gdf['description'].fillna('')
            crimea_mask = crimea_mask | ukr_prov_gdf['description'].str.contains('Krym', case=False, na=False)
        crimea = ukr_prov_gdf[crimea_mask].copy()
        crimea = snap_to_grid(crimea, precision=1e-7)
        crimea_dissolved = crimea.dissolve()
        crimea_dissolved.geometry = crimea_dissolved.geometry.apply(fill_holes)
    else:
        crimea_dissolved = gpd.GeoDataFrame(geometry=[])

    # 1. Dissolve (Melts touching polygons)
    # 2. Fill Holes (Paves over any microscopic internal gaps)
    old_dissolved = old_sm.dissolve()
    old_dissolved.geometry = old_dissolved.geometry.apply(fill_holes)

    new_dissolved = new_sm.dissolve()
    new_dissolved.geometry = new_dissolved.geometry.apply(fill_holes)

    # 3. Dust Filter (Deletes microscopic disconnected floating pixels)
    if not old_dissolved.empty:
        old_dissolved = old_dissolved.explode(index_parts=False)
        old_dissolved = old_dissolved[old_dissolved.geometry.area > 1e-7]

    if not new_dissolved.empty:
        new_dissolved = new_dissolved.explode(index_parts=False)
        new_dissolved = new_dissolved[new_dissolved.geometry.area > 1e-7]

    # --- CALCULATE GAINS ---
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

    # Filter out Crimea from changes
    if not crimea_dissolved.empty:
        if not new_line_area.empty:
            new_line_area = gpd.overlay(new_line_area, crimea_dissolved, how='difference')
        if not old_line_area.empty:
            old_line_area = gpd.overlay(old_line_area, crimea_dissolved, how='difference')

    # Filter by area threshold to remove micro-slivers
    area_thresh = 1e-5
    if not new_line_area.empty:
        new_line_area = new_line_area[new_line_area.geometry.area > area_thresh]

    if not old_line_area.empty:
        old_line_area = old_line_area[old_line_area.geometry.area > area_thresh]

    # Boundaries -> Points
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

    points_ukr = generate_points_along_lines(old_boundaries, 0.003)
    points_ru = generate_points_along_lines(new_boundaries, 0.003)

    # Buffers strictly for filtering pins to the correct side of the frontline
    old_buffered = old_dissolved.copy()
    if not old_buffered.empty:
        old_buffered.geometry = old_buffered.buffer(0.0002)
        old_buffered = old_buffered.dissolve()

    new_buffered = new_dissolved.copy()
    if not new_buffered.empty:
        new_buffered.geometry = new_buffered.buffer(0.0002)
        new_buffered = new_buffered.dissolve()

    # --- FILTER PINS TO TRACE THE *PREVIOUS* LINE ---
    if not points_ukr.empty and not new_buffered.empty:
        points_ukr = gpd.overlay(points_ukr, new_buffered, how='difference')

    if not points_ru.empty and not old_buffered.empty:
        points_ru = gpd.sjoin(points_ru, old_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ru.columns:
            points_ru = points_ru.drop(columns=['index_right'])

    # Label Pins
    if not points_ukr.empty:
        points_ukr['Name'] = 'Ukr gains'
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs if not points_ukr.empty else None)

    if not points_ru.empty:
        points_ru['Name'] = 'Ru gains'
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ru.crs if not points_ru.empty else None)

    # Compile Pins Output
    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], crs=points_ukr.crs)

    # --- COMPILE FINAL MAP OUTPUT ---
    # We use new_dissolved, which is already perfectly snapped, dissolved, and artifact-free!
    map_out = new_dissolved.copy()
    if not map_out.empty:
        map_out = map_out[['geometry']]
        map_out['Name'] = 'Russian controlled'

    if not crimea_dissolved.empty:
        crimea_cleaned = crimea_dissolved.copy()
        crimea_cleaned = crimea_cleaned.explode(index_parts=False).reset_index(drop=True)
        crimea_cleaned = crimea_cleaned[['geometry']]
        crimea_cleaned['Name'] = 'Autonomous Republic of Crimea'
        
        map_out = pd.concat([map_out, crimea_cleaned], ignore_index=True)
        map_out = gpd.GeoDataFrame(map_out, geometry='geometry', crs=new_sm.crs)

    if 'Name' not in map_out.columns:
        map_out['Name'] = ''
        
    return map_out, pins_out
