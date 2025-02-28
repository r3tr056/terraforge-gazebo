# TerraForge Gazebo: Crafting Realistic Simulation Worlds

[![Project Stage](https://img.shields.io/badge/Status-Beta-orange.svg)](https://www.repostatus.org/#beta)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.8+-brightgreen.svg)](https://www.python.org/downloads/)
[![PyQt Version](https://img.shields.io/badge/PyQt-6-brightgreen.svg)](https://www.riverbankcomputing.com/software/pyqt/)


<p align="center">
  <img src="https://github.com/r3tr056/terraforge-gazebo/blob/master/.github/images/banner.png?raw=true" alt="TerraForge Gazebo Logo">
</p>

<p align="center">
  <b>Forge Realistic Gazebo Simulation Environments from Real-World Data with Ease</b>
</p>

<br>

**TerraForge Gazebo** is a powerful Python-based tool designed to automate the creation of high-fidelity, real-world simulation environments within the Gazebo simulator. Built with PyQt for a user-friendly interface, TerraForge Gazebo streamlines the process of generating complex and geographically accurate worlds for testing drones, self-driving vehicles, and robotics applications.

**Imagine:** Instantly creating a Gazebo world that accurately represents a specific location on Earth, complete with terrain elevation, buildings, and satellite imagery. TerraForge Gazebo makes this a reality.

## ✨ Key Features

*   **Intuitive PyQt User Interface:**  A graphical interface for easy world generation, making the tool accessible to users of all levels.
*   **Interactive Map View:**  (Coming Soon!) A Google Earth-like map integration for visually selecting areas of interest, editing regions, and precisely defining simulation boundaries.
*   **Real-World Data Acquisition:**
    *   **Elevation Data (DEM):** Fetches Digital Elevation Models to generate realistic terrain heightmaps.
    *   **OpenStreetMap (OSM) Data:** Downloads building footprints and other geospatial features to populate your simulation with accurate urban or rural structures.
    *   **Satellite Imagery:** Integrates high-resolution satellite textures to overlay onto the terrain, enhancing visual realism.
*   **Automated Data Processing:**
    *   **DEM to Heightmap Conversion:** Processes raw elevation data into Gazebo-compatible heightmap images.
    *   **OSM Building Extrusion:**  Generates simplified 3D building models from OSM footprints for realistic urban environments.
    *   **Texture Tiling and Georeferencing:**  Prepares satellite imagery for seamless integration as terrain textures.
*   **Precise Coordinate Conversion:**  Accurately converts between WGS84 (latitude/longitude), UTM, and Gazebo's coordinate systems, ensuring georeferenced placement of all world elements.
*   **Dynamic SDF World Generation:** Uses Jinja2 templates to generate Gazebo SDF world files dynamically, incorporating terrain, buildings, textures, and custom configurations.
*   **Command-Line Interface (CLI):** Offers a powerful CLI for batch processing and automated world generation pipelines.
*   **Performance Optimized:**  Designed for efficiency with caching, background processing, and optimized data handling to generate worlds quickly and smoothly.
*   **Extensible and Modular Architecture:**  Well-structured Python modules for easy customization, expansion, and contribution.
*   **Comprehensive Testing Suite:**  Includes unit tests to ensure the reliability and correctness of the world generation process.

## 🚀 Getting Started

### Prerequisites

*   **Python 3.8 or higher:**  [Download Python](https://www.python.org/downloads/)
*   **Gazebo Simulator:** [Install Gazebo](http://gazebosim.org/install) (version 11 or newer recommended)
*   **GDAL (Geospatial Data Abstraction Library):**  Required for geospatial data processing. Installation varies by operating system.  See [GDAL Installation Guide](https://gdal.org/download.html) for instructions.
*   **Required Python Packages:** Install dependencies using pip:

    ```bash
    pip install -r requirements.txt
    ```

    *(You'll find `requirements.txt` in the project repository)*

### Installation

1.  **Clone the Repository:**

    ```bash
    git clone https://github.com/r3tr056/terraforge-gazebo.git
    cd TerraForge-Gazebo
    ```

2.  **Install Python Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### Basic Usage

**Using the Command-Line Interface (CLI):**

```bash
python cli/main.py generate-world --latitude <latitude> --longitude <longitude> --radius <radius_meters> --output-dir <output_directory> --world-name <world_name>
```

**Example:**

```bash
python cli/main.py generate-world --latitude 37.7749 --longitude -122.4194 --radius 1000 --output-dir san_francisco_world --world-name san_francisco
```

This command will generate a Gazebo world for San Francisco, California, within a 1km radius, and save it in the `san_francisco_world` directory.

**Using the Graphical User Interface (GUI):**

1.  Navigate to the `gui` directory:

    ```bash
    cd gui
    ```

2.  Run the GUI application:

    ```bash
    python main_window.py
    ```

3.  Enter the desired latitude, longitude, radius, output directory, and world name in the UI.
4.  Click the "Generate World" button.

### Example Output

*(Include screenshots or GIFs of the generated Gazebo world running in Gazebo.  Showcasing terrain, buildings, and textures would be ideal.)*

**Example Gazebo World Screenshot:**

<!-- Example Screenshot (Replace with your actual screenshot) -->
<!-- <p align="center">
  <img src="path/to/your/screenshot.png" alt="Generated Gazebo World Example" width="600">
  <br>
  <em>A Gazebo world generated by TerraForge Gazebo showcasing realistic terrain and building models.</em>
</p> -->

## 🛠️ Project Modules

TerraForge Gazebo is structured into modular components for clarity and maintainability:

*   **`data_acquisition/`**:  Handles fetching geospatial data from various sources (elevation, OSM, textures).
*   **`data_processing/`**: Processes raw data into Gazebo-compatible formats (heightmaps, 3D models, textures).
*   **`coordinate_conversion/`**: Manages coordinate transformations between different geospatial systems.
*   **`sdf_generation/`**:  Generates Gazebo SDF world files using Jinja2 templates.
*   **`cli/`**: Implements the Command-Line Interface using the `click` library.
*   **`gui/`**:  Provides the PyQt-based Graphical User Interface.
*   **`utils/`**: Contains utility modules for configuration, logging, etc.
*   **`tests/`**:  Includes unit tests for core modules to ensure code quality.

## ⚙️ Technology Stack

TerraForge Gazebo leverages the following key technologies:

*   **Python:**  The primary programming language.
*   **PyQt6:**  For building the user-friendly Graphical User Interface.
*   **Gazebo Simulator:**  The target simulation environment.
*   **GDAL (Geospatial Data Abstraction Library):**  For processing geospatial raster and vector data.
*   **elevation Python Library:** For downloading Digital Elevation Models.
*   **osmnx Python Library:** For downloading and working with OpenStreetMap data.
*   **requests Python Library:** For making HTTP requests to download data.
*   **Pillow (PIL Fork):**  For image processing.
*   **pyproj Python Library:** For geospatial coordinate transformations.
*   **shapely Python Library:** For geometric operations on geospatial data.
*   **Jinja2:**  For templating SDF world files.
*   **click Python Library:** For building the Command-Line Interface.
*   **pytest:** For unit testing.
*   **sqlite3:** For optional local tile caching (database feature).
*   **geocoder:** For address geocoding.
*   **Pyperclip:** For clipboard functionality.

## 🤝 Contributing

Contributions are welcome!  If you'd like to contribute to TerraForge Gazebo, please:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and commit them with clear, concise commit messages.
4.  Submit a pull request to the main repository.

Please follow coding style guidelines and include relevant tests with your contributions.

## 📜 License

TerraForge Gazebo is released under the [MIT License](LICENSE).

## 📧 Contact

For questions, bug reports, or feature requests, please [open an issue](link-to-your-issues-page) on GitHub.

---

**Let's forge Gazebo simulations with TerraForge!**
