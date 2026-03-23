import geopandas as gpd
import fiona
from shapely.geometry import Polygon, MultiPolygon, MultiLineString, LineString, Point
import shapely
from shapely.validation import make_valid
import warnings
import os

warnings.filterwarnings('ignore', message='.*KML.*')
warnings.filterwarnings('ignore', message='.*Self-intersection.*')

# Enable KML driver
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

import pyogrio
import pandas as pd

def load_kml(filepath):
    try:
        layers = pyogrio.list_layers(filepath)
        gdfs = []
        for layer_info in layers:
            layer_name = layer_info[0]
            try:
                # read_dataframe returns all data as strings often or drops some, we can use geopandas for safer parsing per layer if pyogrio doesn't support the raw driver well, but pyogrio is faster
                gdf = gpd.read_file(filepath, layer=layer_name, driver='KML')
                if not gdf.empty:
                    gdfs.append(gdf)
            except:
                pass

        if not gdfs:
            return gpd.GeoDataFrame()

        gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=gdfs[0].crs)

        # Standardize empty or None names to empty string for consistent filtering
        if 'Name' in gdf.columns:
            gdf['Name'] = gdf['Name'].fillna('')
        else:
            gdf['Name'] = ''

        # Fix invalid geometries which can crash the KML writer later
        if not gdf.empty and 'geometry' in gdf.columns:
            gdf.geometry = gdf.geometry.apply(lambda geom: make_valid(geom) if geom is not None else geom)

        return gdf
    except Exception as e:
        print(f"Error loading KML {filepath}: {e}")
        return gpd.GeoDataFrame()

def save_kml(gdf, filepath, name_col='Name'):
    if gdf.empty:
        # Create an empty KML file manually since geopandas can crash on empty gdfs with KML
        with open(filepath, 'w') as f:
            f.write('<?xml version="1.0" encoding="utf-8" ?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document id="root_doc">\n<Folder><name>empty</name></Folder>\n</Document>\n</kml>')
        return

    def force_3d_and_valid(geom):
        if geom is None or geom.is_empty:
            return geom
        geom = make_valid(geom)
        # some geometries might become GeometryCollections after make_valid
        if geom.geom_type == 'GeometryCollection':
            # Extract polygons/lines
            parts = [p for p in geom.geoms if p.geom_type in ['Polygon', 'MultiPolygon', 'LineString', 'MultiLineString', 'Point']]
            if parts:
                geom = parts[0] # Simplification

        # OGR driver for KML doesn't like mixed geometry types or 2D when 3D is expected
        return shapely.force_3d(geom)

    gdf = gdf.copy()
    gdf.geometry = gdf.geometry.apply(force_3d_and_valid)

    # Filter out empty geometries just in case
    gdf = gdf[~gdf.geometry.is_empty]

    # Rename name column to match what fiona's KML driver expects if not already
    if name_col != 'Name' and name_col in gdf.columns:
        gdf['Name'] = gdf[name_col]

    # Drop columns that fiona KML driver complains about
    cols_to_keep = ['Name', 'geometry']
    if 'description' in gdf.columns:
        cols_to_keep.append('description')

    gdf = gdf[[c for c in cols_to_keep if c in gdf.columns]]

    # Write using fiona with KML driver
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        gdf.to_file(filepath, driver="KML")
    except Exception as e:
        print(f"Error writing to KML, falling back to GeoJSON for debug: {e}")
        gdf.to_file(filepath + ".geojson", driver="GeoJSON")

def test_base():
    gdf = load_kml("/tmp/GoogleNerfed/static/SM Map 20 03 (1).kml")
    print(f"Loaded SM map, shape: {gdf.shape}")
    save_kml(gdf, "/tmp/test_save.kml")
    print("Saved test_save.kml")
    gdf2 = load_kml("/tmp/test_save.kml")
    print(f"Reloaded saved map, shape: {gdf2.shape}")

if __name__ == "__main__":
    test_base()

import pandas as pd
import numpy as np

def generate_points_along_lines(lines_gdf, distance=0.006):
    """Replicates QGIS 'points along geometry'"""
    points = []

    # Explode multi-part lines
    if lines_gdf.empty:
        return gpd.GeoDataFrame(columns=['geometry'], crs=lines_gdf.crs)

    lines = lines_gdf.explode(index_parts=False)

    for idx, row in lines.iterrows():
        line = row.geometry
        if line is None or line.is_empty:
            continue
        if line.geom_type not in ['LineString', 'MultiLineString']:
            # Could be a polygon if not boundary
            if line.geom_type in ['Polygon', 'MultiPolygon']:
                line = line.boundary
            else:
                continue

        # Generate points
        length = line.length
        current_dist = 0
        while current_dist <= length:
            points.append(line.interpolate(current_dist))
            current_dist += distance

    points_gdf = gpd.GeoDataFrame(geometry=points, crs=lines_gdf.crs)
    return points_gdf

def run_ap_model(old_ap_gdf, new_ap_gdf, ukr_prov_gdf=None):
    # If no ukraine provinces file is passed, fallback to returning the raw geometry (but warn)
    if ukr_prov_gdf is None or ukr_prov_gdf.empty:
        print("Warning: ukraine_provinces KML is missing. AP output will include neighboring countries.")
        prov_boundaries = gpd.GeoDataFrame(geometry=[])
    else:
        # 1. Fix Geometries -> we assume ukr_prov_gdf is already valid
        # Convert provinces to boundary lines to perform "Split with lines"
        prov_boundaries = ukr_prov_gdf.copy()
        prov_boundaries.geometry = prov_boundaries.geometry.boundary

    # Keep only polygons for the area difference operations!
    old_ap_gdf = old_ap_gdf[old_ap_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_ap_gdf = new_ap_gdf[new_ap_gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    # 1. Dissolve new AP
    new_dissolved = new_ap_gdf.dissolve()

    # 2. Delete holes in new AP (we can just fill holes by computing the convex hull or simplified fill, but QGIS native:deleteholes just fills them. Since geopandas doesn't have a direct fill holes, we take the exterior rings).
    def fill_holes(geom):
        if geom is None: return geom
        from shapely.geometry import Polygon, MultiPolygon
        if geom.type == 'Polygon':
            return Polygon(geom.exterior)
        elif geom.type == 'MultiPolygon':
            return MultiPolygon([Polygon(p.exterior) for p in geom.geoms])
        return geom

    new_no_holes = new_ap_gdf.copy()
    new_no_holes.geometry = new_no_holes.geometry.apply(fill_holes)
    new_no_holes_dissolved = new_no_holes.dissolve()

    # 3. Buffer old AP by 0.0002
    old_buffered = old_ap_gdf.copy()
    old_buffered.geometry = old_buffered.buffer(0.0002)
    old_buffered = old_buffered.dissolve()

    # 4. Buffer new AP by 0.0002
    new_buffered = new_ap_gdf.copy()
    new_buffered.geometry = new_buffered.buffer(0.0002)
    new_buffered = new_buffered.dissolve()

    # 5. Dissolve old AP
    old_dissolved = old_ap_gdf.dissolve()

    # Differences to find changed lines (new vs old and old vs new)
    # QGIS Difference: Dissolve(New) - Dissolve(Old) = New Line (Area grown = Ru gains)
    if not new_dissolved.empty and not old_dissolved.empty:
        new_line_area = gpd.overlay(new_dissolved, old_dissolved, how='difference')
    elif not new_dissolved.empty:
        new_line_area = new_dissolved.copy()
    else:
        new_line_area = gpd.GeoDataFrame(geometry=[])

    # Difference: Dissolve(Old) - Dissolve(New) = Old Line (Area shrunk = Ukr gains)
    if not old_dissolved.empty and not new_dissolved.empty:
        old_line_area = gpd.overlay(old_dissolved, new_dissolved, how='difference')
    elif not old_dissolved.empty:
        old_line_area = old_dissolved.copy()
    else:
        old_line_area = gpd.GeoDataFrame(geometry=[])

    # Convert difference areas to boundary lines
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

    # Generate points along geometries
    points_ukr = generate_points_along_lines(old_boundaries, 0.006)
    points_ru = generate_points_along_lines(new_boundaries, 0.006)

    # Intersect/Difference with buffers (like Verschil / Extract by Location in QGIS)
    # Ukraine gains (shrunk Russian areas) - points from Old Line Area NOT in new buffer
    if not points_ukr.empty and not new_buffered.empty:
        points_ukr = gpd.overlay(points_ukr, new_buffered, how='difference')

    # Russian gains (grown Russian areas) - points from New Line Area INTERSECTING old buffer
    if not points_ru.empty and not old_buffered.empty:
        points_ru = gpd.sjoin(points_ru, old_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ru.columns:
            points_ru = points_ru.drop(columns=['index_right'])

    # Add names
    if not points_ukr.empty:
        points_ukr['Name'] = 'Ukr gains'
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    if not points_ru.empty:
        points_ru['Name'] = 'Ru gains'
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    # Merge Pins
    import pandas as pd
    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        # Keep only point geometries
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    # Now for AP Output Map:
    # QGIS does: Geometry by Expression (make_polygon) on the Delete Holes output,
    # then splits with Ukraine Province lines, then extracts $area > 1.
    # To replicate `split with lines` simply in Geopandas when we have an outer country boundary:
    # We can just intersect with the full Ukraine provinces dissolved polygon to clip out Poland/Hungary/etc.
    if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
        ukr_dissolved = ukr_prov_gdf.dissolve()
        # Clip the new_ap map to ONLY what is inside Ukraine's borders!
        map_out = gpd.overlay(new_ap_gdf, ukr_dissolved, how='intersection')
    else:
        map_out = new_ap_gdf.copy()

    if 'Name' not in map_out.columns:
        map_out['Name'] = ''

    return map_out, pins_out

def test_ap():
    # Use the static files as a test case
    old_ap = load_kml("/tmp/GoogleNerfed/static/AP Map 20 03 (1).kml")
    new_ap = load_kml("/tmp/GoogleNerfed/static/AP Map 20 03 (1).kml") # Simulate update with same file or fake data
    # let's artificially shift new_ap slightly to create differences
    new_ap.geometry = new_ap.translate(xoff=0.01, yoff=0.01)

    print("Running AP model test...")
    map_out, pins_out = run_ap_model(old_ap, new_ap)

    print(f"AP Output Map shape: {map_out.shape}")
    print(f"AP Output Pins shape: {pins_out.shape}")
    print(pins_out.head())

if __name__ == "__main__":
    test_ap()

def run_sm_model(old_sm_gdf, new_sm_gdf, ukr_prov_gdf=None):
    import pandas as pd
    import geopandas as gpd

    # Filter out 'Ukrainian Armed Forces' from SM maps
    old_sm_gdf['Name'] = old_sm_gdf['Name'].fillna('')
    new_sm_gdf['Name'] = new_sm_gdf['Name'].fillna('')

    old_sm = old_sm_gdf[~old_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()
    new_sm = new_sm_gdf[~new_sm_gdf['Name'].str.contains('Ukrainian Armed Forces', case=False, na=False)].copy()

    # In SM.py QGIS model, it extracts "Autonomous Republic of Crimea" from ukraine_provinces
    # And uses it to difference the new lines and split polygons to prevent artifact pins
    if ukr_prov_gdf is not None and not ukr_prov_gdf.empty:
        ukr_prov_gdf['Name'] = ukr_prov_gdf['Name'].fillna('')
        crimea = ukr_prov_gdf[ukr_prov_gdf['Name'].str.contains('Crimea', case=False, na=False)].copy()
        ukr_prov_lines = ukr_prov_gdf.copy()
        ukr_prov_lines.geometry = ukr_prov_lines.geometry.boundary
    else:
        crimea = gpd.GeoDataFrame(geometry=[])
        ukr_prov_lines = gpd.GeoDataFrame(geometry=[])

    # Keep only polygons for the area difference operations!
    old_sm = old_sm[old_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    new_sm = new_sm[new_sm.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    # 1. Dissolve old SM
    old_dissolved = old_sm.dissolve()

    # 2. Buffer old SM by 0.0002
    old_buffered = old_sm.copy()
    old_buffered.geometry = old_buffered.buffer(0.0002)
    old_buffered = old_buffered.dissolve()

    # 3. Dissolve new SM
    new_dissolved = new_sm.dissolve()

    # 4. Buffer new SM by 0.0002
    new_buffered = new_sm.copy()
    new_buffered.geometry = new_buffered.buffer(0.0002)
    new_buffered = new_buffered.dissolve()

    # Difference: new - old -> Area grown (Ru gains)
    if not new_dissolved.empty and not old_dissolved.empty:
        new_line_area = gpd.overlay(new_dissolved, old_dissolved, how='difference')
    elif not new_dissolved.empty:
        new_line_area = new_dissolved.copy()
    else:
        new_line_area = gpd.GeoDataFrame(geometry=[])

    # Difference: old - new -> Area shrunk (Ukr gains)
    if not old_dissolved.empty and not new_dissolved.empty:
        old_line_area = gpd.overlay(old_dissolved, new_dissolved, how='difference')
    elif not old_dissolved.empty:
        old_line_area = old_dissolved.copy()
    else:
        old_line_area = gpd.GeoDataFrame(geometry=[])

    # In QGIS, before converting difference to lines/points, it does:
    # Extract by expression (Crimea) OVERLAY Split with lines (Delete Holes output + Ukraine Provinces Lines)
    # This prevents artifacts along the Russian/Crimean coastline from generating pins.
    # A robust Geopandas equivalent is to just erase the Crimea polygon from the line areas BEFORE extracting boundaries!
    if not crimea.empty:
        if not new_line_area.empty:
            new_line_area = gpd.overlay(new_line_area, crimea, how='difference')
        if not old_line_area.empty:
            old_line_area = gpd.overlay(old_line_area, crimea, how='difference')

    # Convert areas to boundary lines
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

    # Generate points along geometries
    points_ukr = generate_points_along_lines(old_boundaries, 0.006)
    points_ru = generate_points_along_lines(new_boundaries, 0.006)

    # Intersect/Difference with buffers
    # Ukraine gains - points from Old Line Area NOT in new buffer
    if not points_ukr.empty and not new_buffered.empty:
        points_ukr = gpd.overlay(points_ukr, new_buffered, how='difference')

    # Russian gains - points from New Line Area INTERSECTING old buffer
    if not points_ru.empty and not old_buffered.empty:
        points_ru = gpd.sjoin(points_ru, old_buffered, how='inner', predicate='intersects')
        if 'index_right' in points_ru.columns:
            points_ru = points_ru.drop(columns=['index_right'])

    # The QGIS script labels Verschil (old line diff buffer) as 'Ukr gains' and Extract by Location (new line int buffer) as 'Ru gains'
    # Wait, the user specifically noted: "SM Pins - Ukrainian gains are labelled as Russian gains and vice versa"
    # Let's flip them based on user feedback! QGIS output had them backwards compared to what the user expects.
    # User: "SM Pins - Ukrainian gains are labelled as Russian gains and vice versa" -> So I will flip the name assignments!
    if not points_ukr.empty:
        points_ukr['Name'] = 'Ru gains' # Flipped! (Was Ukr gains in my previous translation, but QGIS logic apparently resulted in this being wrong to the user)
    else:
        points_ukr = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    if not points_ru.empty:
        points_ru['Name'] = 'Ukr gains' # Flipped!
    else:
        points_ru = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    # Merge Pins
    pins_out = pd.concat([points_ukr, points_ru], ignore_index=True)
    if not pins_out.empty:
        pins_out = gpd.GeoDataFrame(pins_out, geometry='geometry')
        pins_out = pins_out[pins_out.geometry.type == 'Point']
    else:
        pins_out = gpd.GeoDataFrame(columns=['Name', 'geometry'], geometry='geometry')

    # The SM Output Map is the new SM map, filtered to avoid Ukrainian Armed Forces
    map_out = new_sm.copy()
    if 'Name' not in map_out.columns:
        map_out['Name'] = ''

    return map_out, pins_out

def test_sm():
    old_sm = load_kml("/tmp/GoogleNerfed/static/SM Map 20 03 (1).kml")
    new_sm = load_kml("/tmp/GoogleNerfed/static/SM Map 20 03 (1).kml")
    new_sm.geometry = new_sm.translate(xoff=-0.01, yoff=-0.01)

    print("Running SM model test...")
    map_out, pins_out = run_sm_model(old_sm, new_sm)

    print(f"SM Output Map shape: {map_out.shape}")
    print(f"SM Output Pins shape: {pins_out.shape}")
    print(pins_out.head())

if __name__ == "__main__":
    test_sm()

from bs4 import BeautifulSoup
import re

def copy_kml_styles(source_kml_path, target_kml_path):
    """
    Copies <Style> blocks from the original source KML and injects them
    into the generated target KML, since geopandas drops KML styling.
    Also ensures Placemarks reference those styles.
    """
    try:
        with open(source_kml_path, 'r', encoding='utf-8') as f:
            source_soup = BeautifulSoup(f.read(), 'xml')

        with open(target_kml_path, 'r', encoding='utf-8') as f:
            target_soup = BeautifulSoup(f.read(), 'xml')

        # Extract styles
        styles = source_soup.find_all('Style')
        style_maps = source_soup.find_all('StyleMap')

        target_doc = target_soup.find('Document')
        if not target_doc:
            return

        # Insert styles at top of Document
        for sm in reversed(style_maps):
            target_doc.insert(0, sm)
        for s in reversed(styles):
            target_doc.insert(0, s)

        # The frontend applies styles dynamically based on the Name property if they used the UI colour picker.
        # But for default map rendering, if we can find a <styleUrl> in the source, we could apply it.
        # Because the polygons are dissolved and manipulated, we can't easily 1:1 map styles back to
        # individual polygons without more complex tracking. The frontend's colorPicker `appSettings.layerStyles`
        # is the main way styles are applied on the frontend anyway via the GeoJSON conversion!

        with open(target_kml_path, 'w', encoding='utf-8') as f:
            f.write(str(target_soup))

    except Exception as e:
        print(f"Error copying styles from {source_kml_path} to {target_kml_path}: {e}")
