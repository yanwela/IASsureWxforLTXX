# IASsure TR Weather Feeder

This service is designed to gather weather data to be used by IASsure by MorpheusXAUT. It uses the Open-Meteo.com-API to gather the necessary data to provide to the plugin.

## Purpose

The IASsure EuroScope plugin requires a three-dimensional wind and temperature matrix to estimate aircraft Indicated Airspeed (IAS) and Mach numbers. The primary objectives of this script are:
* To optimize data traffic and processing load by focusing exclusively on the Turkish Airspace (LTBB and LTAA FIRs) rather than fetching global meteorological datasets.
* To gather real-time weather data across 12 aviation-standard pressure levels (from FL000 up to FL390) using the Open-Meteo API.
* To process and transform the raw data into a minified, single-line `weather.json` schema compatible with the plugin, including a mathematical conversion of Celsius temperatures to the Kelvin scale.

## Core Logic

The system operates as a continuous background daemon that triggers a synchronous weather update cycle every 1 hour. The execution sequence follows these steps:

1. **Boundary Retrieval:** Fetches live GeoJSON boundary data from the VATSpy Data Project repository.
2. **FIR Filtering:** Scans the global dataset to isolate the geometric polygons corresponding specifically to the `LTBB` (Istanbul) and `LTAA` (Ankara) FIR areas.
3. **Grid Generation and Validation:** Scans the targeted airspace geometry to generate a filtered coordinate matrix.
4. **Weather Retrieval:** Sends a bulk API request to Open-Meteo for all validated grid coordinates, pulling wind speed (in knots), wind direction, and temperature data across the 12 distinct flight levels.
5. **Schema Transformation:** Reconstructs the raw dataset by mapping pressure levels, converting temperatures to Kelvin, and assigning short, distinct identifiers (`TRG01`, `TRG02`, etc.) to each node.
6. **Deployment:** Exports the fully formatted dataset into a minified, single-line `weather.json` file.

## Grid Calculation and Discovery

The core geospatial intelligence of the script relies on the Shapely library for advanced geometric evaluations. Finding and validating grid points is achieved through a three-stage mathematical workflow:

### 1. Bounding Box Generation
The system reads the extreme coordinate boundaries of the filtered `LTBB` and `LTAA` polygons. By extracting these spatial boundaries, it establishes the smallest possible virtual bounding box rectangle that completely encompasses the targeted airspace using four key variables:
* `min_lon` (Westernmost boundary point)
* `min_lat` (Southernmost boundary point)
* `max_lon` (Easternmost boundary point)
* `max_lat` (Northernmost boundary point)

### 2. Two-Dimensional Matrix Scanning
Starting from the bottom-left corner (`min_lat`, `min_lon`) of the bounding box, the script runs nested loops stepping toward the top-right corner (`max_lat`, `max_lon`). Coordinates are incremented linearly based on the `grid_interval=1.5` parameter, skipping roughly 90 nautical miles per step to generate sanal coordinate samples.

### 3. Polygon Containment Filtering (The Sieve)
Although every generated sample point falls inside the rectangular bounding box, it is not automatically accepted. Each coordinate point is evaluated via the `poly.contains()` function against the true geometric boundaries of the Istanbul and Ankara FIR polygons:
* Points falling outside the actual FIR boundaries (e.g., inside neighboring countries' landmasses or open waters outside the FIR) are mathematically discarded.
* Points falling strictly within the defined Turkish Airspace boundaries are validated and appended to the final `our_coordinates` list.

This sieve algorithm ensures that the script only queries and provides weather cells that directly impact the controlled airspace, feeding the plugin's interpolation engine with an optimized and highly accurate data matrix.

## Credits
* Developer: alp-1863530
