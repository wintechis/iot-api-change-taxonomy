import json
import os
from enum import Enum
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Filter out issues that have already be manually annotated
from pydantic import BaseModel, Field, field_serializer

OPENAI_KEY: str = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)


SYSTEM_PROMPT = """
You are an AI assistant specialized in analyzing software development discussions, particularly those related to API changes. 
Your task is to accurately determine if the given content is about API changes and provide a structured analysis.
Use the following taxonomy and requirements to classify the API change type, and select one or several leaf categories (any category without any more detailed category) that best describe the content:

## Taxonomy of IoT API Changes:
* Data Payload Modifications: Changes to the structure, format, or content of the data exchanged between IoT devices and systems through the API, applicable to diverse IoT communication methods.
    * Modify Data Payload Format:
        * Definition: Changing the serialization or encoding format used for the payload data.
        * Example: Switching from a proprietary binary format to Protocol Buffers (Protobuf) to improve cross-platform compatibility between devices from different manufacturers.
    * Modify Data Type:
        * Definition: Altering the data type of specific fields within the payload.
        * Example: Changing sensor data from 16-bit integers to 32-bit floating-point numbers to accommodate higher precision measurements in industrial IoT applications.
    * Modify Structure of Payload:
        * Definition: Restructuring the organization or schema of data elements within the payload.
        * Example: Redesigning a payload in a Zigbee network to include nested clusters for efficient grouping of related device attributes.
    * Modify Encoding of Payload:
        * Definition: Altering the character or data encoding scheme used for the payload.
        * Example: Changing from ASCII to UTF-16 encoding to support a wider range of characters in internationalized smart city applications.
    * Modify Payload Compression:
        * Definition: Changing the compression algorithm or method used to reduce payload size.
        * Example: Implementing LZ4 compression instead of GZIP in LoRaWAN networks to decrease transmission time and conserve energy in battery-powered sensors.
    * Modify Consumed Data Payload:
        * Definition: Altering the structure or content of data that the API receives from devices.
        * Example: Adding a new field for GPS coordinates in data sent by autonomous drones to include location information alongside sensor readings.
    * Modify Produced Data Payload:
        * Definition: Changing the structure or content of data that the API sends to devices.
        * Example: Including predictive maintenance alerts in data transmitted to industrial machines to preempt equipment failures.

* Communication Protocol Modifications: Changes to the communication protocols or technologies used for data exchange between IoT devices and systems, covering a variety of IoT-specific protocols.
    * Modify Protocol:
        * Definition: Replacing the communication protocol with a different one better suited to the application's requirements.
        * Example: Switching from Zigbee to Bluetooth Low Energy (BLE) to improve device interoperability and reduce power consumption in wearable health monitors.
    * Modify Protocol Version:
        * Definition: Updating to a newer version of the same protocol to leverage improvements.
        * Example: Upgrading from Bluetooth 4.2 to Bluetooth 5.0 to benefit from increased range and data transfer rates in smart home lighting systems.
    * Add Protocol Feature:
        * Definition: Enabling additional features or extensions within the existing protocol.
        * Example: Implementing mesh networking capabilities in a Thread protocol to enhance connectivity in a home automation system.

* API Endpoint Modifications: Changes to the access points or interfaces through which IoT devices interact with the API, applicable across various IoT communication methods beyond web URLs.
    * Add Endpoint:
        * Definition: Introducing a new interface or command for additional functionalities.
        * Example: Adding a new function code in a Modbus protocol implementation to support remote device diagnostics in industrial equipment.
    * Remove Endpoint:
        * Definition: Eliminating an existing interface or command from the API.
        * Example: Removing an outdated CAN bus message identifier no longer used in vehicle telemetry systems.
    * Rename Endpoint:
        * Definition: Changing the identifier or name of an existing interface or command.
        * Example: Renaming a CoAP (Constrained Application Protocol) resource from /sensor/old_data to /sensor/current_data to reflect updated functionality.
    * Relocate Endpoint:
        * Definition: Moving an interface or command to a different address or identifier within the API structure.
        * Example: Changing the address of a BACnet object in a building automation system to align with a new device numbering scheme.
    * Split Endpoint:
        * Definition: Dividing a single interface or command into multiple ones offering more specific functionalities.
        * Example: Splitting a general control command into separate start, stop, and pause commands in an OPC UA server managing manufacturing robots.
    * Combine Endpoint:
        * Definition: Merging multiple interfaces or commands into a single one that consolidates their functionalities.
        * Example: Combining separate read and write operations into a single read/write command to simplify interactions.
    * Modify Access Method to Endpoint:
        * Definition: Changing the method or operation code used to interact with an interface, command, service, or resource.
        * Example: Altering a command in a Zigbee network from unicast to broadcast to efficiently send updates to all devices in a group, or switching from POST to PUT in a RESTful API to update resource data..

* Security Modifications: Changes to the authentication, authorization, and encryption mechanisms of the API, applicable across various IoT technologies and protocols.
    * Modify Authentication Method:
        * Definition: Changing how devices or users are authenticated within the system.
        * Example: Implementing mutual authentication using X.509 certificates in devices that previously relied on simple pre-shared keys.
    * Modify Authorization Method:
        * Definition: Changing how access rights and permissions are managed for authenticated entities.
        * Example: Introducing role-based access control (RBAC) in an industrial control system to provide granular permissions based on user roles.
    * Modify Encryption:
        * Definition: Updating the encryption algorithms or protocols used to secure data transmission.
        * Example: Upgrading from AES-128 to AES-256 encryption in wireless sensor networks to enhance data security against potential threats.

* Parameter Modifications: Changes to the input and output parameters of API methods or commands across different IoT protocols and devices.
    * Add Parameter:
        * Definition: Introducing a new parameter to a method or command.
        * Example: Adding a quality_of_service parameter in MQTT messages to allow devices to specify the reliability level of message delivery.
    * Remove Parameter:
        * Definition: Eliminating an existing parameter from a method or command.
        * Example: Removing a redundancy parameter that is no longer needed due to improved network stability in a mesh network.
    * Rename Parameter:
        * Definition: Changing the name of a parameter without altering its functionality.
        * Example: Renaming a parameter from temp_reading to temperature_value for consistency across different devices in a sensor network.
    * Modify Parameter Upper Bound:
        * Definition: Changing the maximum allowable value for a numeric parameter.
        * Example: Increasing the upper limit of a data_rate parameter from 1 Mbps to 2 Mbps to support higher bandwidth requirements in video surveillance systems.
    * Modify Parameter Lower Bound:
        * Definition: Changing the minimum allowable value for a numeric parameter.
        * Example: Decreasing the minimum value of a signal_threshold parameter in a wireless communication system to improve connectivity in areas with weak signals.
    * Modify Default Value of Parameter:
        * Definition: Changing the default value assigned to a parameter when not specified by the client.
        * Example: Adjusting the default power_mode from active to sleep in battery-powered IoT devices to extend battery life when idle.
    * Reorder Parameter:
        * Definition: Changing the sequence in which parameters are expected or processed in a method or command.
        * Example: Rearranging parameters in a Modbus function code to align with updated protocol standards for better interoperability.


## Requirements:
- The 'class_type' should be the identified API type from the list, another recognized type, or 'Unknown' if no specific type can be determined.
- If the content is ambiguous or lacks sufficient information, classify it as 'Unknown'.
- The 'confidence' should be a float between 0 and 1, indicating your confidence in the assessment.
- The 'explanation' should provide a brief rationale for your decision, referencing specific parts of the content if applicable.
- Ensure your response is a valid JSON object and nothing else.
"""
CLASSIFICATION_PROMPT = """
## Content to analyze:
### Title: {title}
### Body:
{content}
### Comments:
{comments}

"""


class IoTAPIChanges(str, Enum):
    modifyDataPayloadFormat = "Modify Data Payload Format"
    modifyDataType = "Modify Data Type"
    modifyStructureOfPayload = "Modify Structure of Payload"
    modifyEncodingOfPayload = "Modify Encoding of Payload"
    modifyPayloadCompression = "Modify Payload Compression"
    modifyConsumedDataPayload = "Modify Consumed Data Payload"
    modifyProducedDataPayload = "Modify Produced Data Payload"
    modifyProtocol = "Modify Protocol"
    modifyProtocolVersion = "Modify Protocol Version"
    addProtocolFeature = "Add Protocol Feature"
    addEndpoint = "Add Endpoint"
    removeEndpoint = "Remove Endpoint"
    renameEndpoint = "Rename Endpoint"
    relocateEndpoint = "Relocate Endpoint"
    splitEndpoint = "Split Endpoint"
    combineEndpoint = "Combine Endpoint"
    modifyAccessMethodToEndpoint = "Modify Access Method to Endpoint"
    modifyAuthenticationMethod = "Modify Authentication Method"
    modifyAuthorizationMethod = "Modify Authorization Method"
    modifyEncryption = "Modify Encryption"
    modifyAccessControlPolicy = "Modify Access Control Policy"
    addParameter = "Add Parameter"
    removeParameter = "Remove Parameter"
    renameParameter = "Rename Parameter"
    modifyParameterUpperBound = "Modify Parameter Upper Bound"
    modifyParameterLowerBound = "Modify Parameter Lower Bound"
    modifyDefaultValueOfParameter = "Modify Default Value of Parameter"
    reorderParameter = "Reorder Parameter"
    unknown = "Unknown"


# Fix to allow the enum to be serialized for the structured output of chatgpt
IoTAPIChangesList = [
    IoTAPIChanges.modifyDataPayloadFormat,
    IoTAPIChanges.modifyDataType,
    IoTAPIChanges.modifyStructureOfPayload,
    IoTAPIChanges.modifyEncodingOfPayload,
    IoTAPIChanges.modifyPayloadCompression,
    IoTAPIChanges.modifyConsumedDataPayload,
    IoTAPIChanges.modifyProducedDataPayload,
    IoTAPIChanges.modifyProtocol,
    IoTAPIChanges.modifyProtocolVersion,
    IoTAPIChanges.addProtocolFeature,
    IoTAPIChanges.addEndpoint,
    IoTAPIChanges.removeEndpoint,
    IoTAPIChanges.renameEndpoint,
    IoTAPIChanges.relocateEndpoint,
    IoTAPIChanges.splitEndpoint,
    IoTAPIChanges.combineEndpoint,
    IoTAPIChanges.modifyAccessMethodToEndpoint,
    IoTAPIChanges.modifyAuthenticationMethod,
    IoTAPIChanges.modifyAuthorizationMethod,
    IoTAPIChanges.modifyEncryption,
    IoTAPIChanges.modifyAccessControlPolicy,
    IoTAPIChanges.addParameter,
    IoTAPIChanges.removeParameter,
    IoTAPIChanges.renameParameter,
    IoTAPIChanges.modifyParameterUpperBound,
    IoTAPIChanges.modifyParameterLowerBound,
    IoTAPIChanges.modifyDefaultValueOfParameter,
    IoTAPIChanges.reorderParameter,
    IoTAPIChanges.unknown,
]


class APITaxonomyClassification(BaseModel):
    class_type: str = Field(
        description="The detected color", json_schema_extra={"enum": IoTAPIChangesList}
    )
    confidence: float = Field(
        alias="api_taxonomy_class_confidence",
        description="Confidence of the classification. ",
        example=0.9,
    )
    explanation: str = Field(
        alias="api_taxonomy_class_explanation",
        description="Explanation of the classification",
        example="The issue is related to the configuration of the integration",
    )


class APITaxonomyClassificationList(BaseModel):
    api_taxonomy_classes: List[APITaxonomyClassification]


class Comment(BaseModel):
    id: int = Field(description="Comment id", example=1671166094)
    body: str = Field(
        description="Comment body", example="Netdata integration is not working"
    )

    class Config:
        # enable other fields to be passed
        # to the model and to be saved in the model
        extra = "allow"


class Issue(BaseModel):
    number: int = Field(description="Issue number", example=1)
    title: str = Field(
        description="Issue title", example="Netdata integration not working"
    )
    created: str = Field(
        description="Date the issue was created", example="2021-01-01 18:07:34+00:00"
    )
    updated: str = Field(
        description="Date the issue was last updated",
        example="2021-01-01 18:07:34+00:00",
    )
    closed: Optional[str] = Field(
        description="Date the issue was closed", example="2021-01-01 18:07:34+00:00"
    )
    body: Optional[str] = Field(
        description="Issue body", example="Netdata integration is not working"
    )
    comments: List[Comment] = Field(
        description="Comments on the issue", example=["I am having the same issue"]
    )
    api_taxonomy_class: Optional[APITaxonomyClassification] = None

    class Config:
        # enable other fields to be passed
        # to the model and to be saved in the model
        extra = "allow"
        # enable alias as key of the json document
        populate_by_name = True


### LOAD THE DATA
with open(
    "../processed/19-09-2024-home_assistant_issues_screened_and_reconciled_and_processed_and_enriched_with_involved_iot_apis_new_descriptions.json",
    "r",
) as f:
    data = json.load(f)
    issues = data["issues"]
    new_taxonomy_issues = [Issue(**issue) for issue in issues]


### ANALYZE THE CONTENT
def analyze_content(
    title: str, body: str, comments: List[str]
) -> APITaxonomyClassificationList:
    prompt = CLASSIFICATION_PROMPT.replace("{content}", body)
    prompt = prompt.replace("{title}", title)

    number_of_comments = len(comments)
    for i in [number_of_comments, 0]:
        insert_prompt = prompt.replace("{comments}", "\n".join(comments[:i]))
        try:
            response = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": insert_prompt},
                ],
                temperature=0.0,
                response_format=APITaxonomyClassificationList,
            )

            result = json.loads(response.choices[0].message.content)
            return APITaxonomyClassificationList(**result)
        except Exception as e:
            print(e)


for num, issue in enumerate(new_taxonomy_issues):
    if issue.api_taxonomy_class:
        continue
    body = issue.body
    title = issue.title
    comments = [comment.body for comment in issue.comments]

    if (body is None) and (title is None):
        issue.api_taxonomy_class = APITaxonomyClassification(
            class_type="Unknown", confidence=0.0, explanation="No content to analyze"
        )
    if body is None:
        body = ""
    if title is None:
        title = ""
    classes = analyze_content(title, body, comments)

    if classes is None:
        issue.api_taxonomy_class = APITaxonomyClassification(
            class_type="Unknown", confidence=0.0, explanation="No content to analyze"
        )
    else:
        issue.api_taxonomy_class = classes
    print(f"Num: {num} | {issue.api_taxonomy_class}")

### SAVE THE RESULTS
with open(
    "../processed/20-09-2024-home_assistant_issues_screened_and_reconciled_and_processed_and_enriched_with_involved_iot_apis_new_descriptions_new_classification_updated_large_model_less_restrictive.json",
    "w",
) as f:
    res = []
    for issue in new_taxonomy_issues:
        _ = issue.dict()

        if issue.api_taxonomy_class is not None:
            _["api_taxonomy_class"] = issue.api_taxonomy_class.dict()
        else:
            _["api_taxonomy_class"] = {
                "api_taxonomy_classes": [
                    {
                        "class_type": "Unknown",
                        "confidence": 0.9,
                        "explanation": "The content discusses an issue with device detection in an integration but does not explicitly mention any API changes or modifications.",
                    }
                ]
            }
        res.append(_)

    data = {"issues": res}
    f.write(json.dumps(data, indent=4))
