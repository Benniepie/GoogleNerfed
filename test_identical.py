import logging
from shapely.geometry import Polygon
import geopandas as gpd
from geoprocessing import run_ap_model, run_sm_model

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_identical')

def test_identical():
    logger.info("Generating mock data for testing identical inputs...")
    poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    mock_data = gpd.GeoDataFrame({'Name': ['Test', 'Russian'], 'LayerName': ['Test', 'Russian'], 'geometry': [poly1, poly1]}, crs="EPSG:4326")

    logger.info("Running AP model with identical old/new inputs...")
    ap_map, ap_pins = run_ap_model(mock_data, mock_data)
    logger.info(f"AP Map out features: {len(ap_map)}")
    logger.info(f"AP Pins out features: {len(ap_pins)}")
    assert len(ap_pins) == 0, f"Expected 0 pins for identical AP inputs, got {len(ap_pins)}"

    logger.info("Running SM model with identical old/new inputs...")
    sm_map, sm_pins = run_sm_model(mock_data, mock_data)
    logger.info(f"SM Map out features: {len(sm_map)}")
    logger.info(f"SM Pins out features: {len(sm_pins)}")
    assert len(sm_pins) == 0, f"Expected 0 pins for identical SM inputs, got {len(sm_pins)}"

    logger.info("Identical inputs generated no garbage pins successfully.")

if __name__ == '__main__':
    test_identical()
