import json
import re
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

# Constants
INPUT_FILE_PATH: str = "../datasets/raw/integrations_from_homeassistant.json"
OUTPUT_FILE_PATH: str = "../data/interim/iot_integrations.json"
HOMEASSISTANT_USERS: int = 279272  # see https://analytics.home-assistant.io/statistics/
VALID_IOT_CLASSES: List[str] = [
    "Local Polling",
    "Cloud Polling",
    "Local Push",
    "Cloud Push",
]
VALID_IOT_CATEGORY = [
    "Alarm",
    "Automation",
    "Binary Sensor",
    "Button",
    "Camera",
    "Car",
    "Climate",
    "Cover",
    "Device automation",
    "Device tracker",
    "Doorbell",
    "Energy",
    "Environment",
    "Fan",
    "Health",
    "Hub",
    "Humidifier",
    "Image",
    "Irrigation",
    "Lawnmower",
    "Light",
    "Lock",
    "Media player",
    "Media source",
    "Number",
    "Plug",
    "Presence detection",
    "Scene",
    "Select",
    "Sensor",
    "Siren",
    "Switch",
    "Transport",
    "Vaccum",
    "Valve",
    "Voice",
    "Water heater",
    "Weather",
]


class IntegrationInfo(BaseModel):
    """Represents information about a Home Assistant integration."""

    api: str
    introduction_version: str
    iot_class: str
    content: str
    categories: List[str]
    deployment_type: Optional[str] = Field(
        default="", description="Type of integration (local or cloud)"
    )
    communication_mechanism: Optional[str] = Field(
        default="", description="Communication mechanism used by the integration"
    )


def extract_integration_info(html_content: str, api: str) -> Optional[IntegrationInfo]:
    """
    Extract integration information from HTML content.

    Args:
        html_content (str): The HTML content of the integration page.
        api (str): The API URL of the integration.

    Returns:
        Optional[IntegrationInfo]: Extracted integration information, or None if extraction fails.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    sidebar = soup.find("aside", id="integration-sidebar")
    if not sidebar:
        print(f"Could not find the integration sidebar for {api}")
        return None

    intro_section = sidebar.find("section", class_="aside-module")
    if not intro_section:
        print(f"Could not find the intro section in the sidebar for {api}")
        return None

    intro_text = intro_section.text.strip()

    introduction_version = extract_introduction_version(intro_text)
    iot_class = extract_iot_class(intro_section.get_text())

    content_elem = soup.find("article", class_="page")
    content = content_elem.decode_contents() if content_elem else ""

    categories = extract_categories(soup)

    integration_info = IntegrationInfo(
        api=api,
        introduction_version=introduction_version,
        iot_class=iot_class,
        content=content,
        categories=categories,
    )

    integration_info.deployment_type = (
        "Cloud" if "cloud" in iot_class.lower() else "Local"
    )
    integration_info.communication_mechanism = (
        "Push" if "push" in iot_class.lower() else "Polling"
    )

    return integration_info


def extract_introduction_version(intro_text: str) -> str:
    """Extract the introduction version from the intro text."""
    intro_match = re.search(r"introduced in Home Assistant ([\d.]+)", intro_text)
    return intro_match.group(1) if intro_match else "Unknown"


def extract_iot_class(intro_section_text: str) -> str:
    """Extract the IoT class from the intro section text."""
    iot_class_match = re.search(r"Its IoT class is (.+?)\.", intro_section_text)
    return iot_class_match.group(1) if iot_class_match else "Unknown"


def extract_categories(soup: BeautifulSoup) -> List[str]:
    """Extract categories from the BeautifulSoup object."""
    categories_section = soup.find("section", id="category-module")
    if categories_section:
        category_links = categories_section.find_all("a")
        return [link.text.strip() for link in category_links]
    return []


def fetch_integration_info(url: str) -> Optional[IntegrationInfo]:
    """
    Fetch and extract integration information from a given URL.

    Args:
        url (str): The URL of the integration page.

    Returns:
        Optional[IntegrationInfo]: Extracted integration information, or None if fetching fails.
    """
    response = requests.get(url)
    if response.status_code == 200:
        return extract_integration_info(response.text, url)
    else:
        print(f"Failed to fetch {url}")
        return None


def load_integration_urls(file_path: str) -> List[str]:
    """Load integration URLs from a JSON file."""
    with open(file_path, "r") as f:
        data = json.load(f)
    return [f"https://www.home-assistant.io/{item['url']}" for item in data]


def save_integrations(integrations: List[IntegrationInfo], file_path: str):
    """Save integration information to a JSON file."""
    res = []
    for integration in integrations:
        valid_iot_class: bool = integration.iot_class in VALID_IOT_CLASSES
        valid_iot_category: bool = any(
            category in integration.categories for category in VALID_IOT_CATEGORY
        )
        if valid_iot_class and valid_iot_category:
            res.append(integration.dict())

    data = {"search_results": res}
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    """Main function to orchestrate the integration scraping workflow."""
    urls = load_integration_urls(INPUT_FILE_PATH)
    integrations = []

    for url in urls:
        integration_info = fetch_integration_info(url)
        if integration_info:
            print(integration_info)
            integrations.append(integration_info)

    save_integrations(integrations, OUTPUT_FILE_PATH)
    print(f"Data saved to {OUTPUT_FILE_PATH}")


if __name__ == "__main__":
    main()
