import json

from app.api.v1.logbooks import normalize_logbook_payload


def test_normalize_logbook_payload_supports_component_parts_json_string():
    parsed = normalize_logbook_payload(
        {
            "component_parts": json.dumps(
                [
                    {
                        "qty": 1,
                        "unit": "EA",
                        "nomenclature": "Seat Rail",
                        "removedPartNo": "OLD-1",
                        "removedSerialNo": "SN-OLD-1",
                        "installedPartNo": "NEW-1",
                        "installedSerialNo": "SN-NEW-1",
                        "ataChapter": "25",
                    }
                ]
            )
        }
    )

    assert parsed["component_parts"] == [
        {
            "qty": 1,
            "unit": "EA",
            "nomenclature": "Seat Rail",
            "removed_part_no": "OLD-1",
            "removed_serial_no": "SN-OLD-1",
            "installed_part_no": "NEW-1",
            "installed_serial_no": "SN-NEW-1",
            "ata_chapter": "25",
        }
    ]


def test_normalize_logbook_payload_supports_component_parts_camel_case_items():
    parsed = normalize_logbook_payload(
        {
            "componentParts": [
                {
                    "id": "123",
                    "qty": 2,
                    "unit": "EA",
                    "nomenclature": "GPS Tray",
                    "removedPartNo": "OLD-2",
                    "installedPartNo": "NEW-2",
                    "ataChapter": "34",
                }
            ]
        }
    )

    assert parsed["component_parts"] == [
        {
            "id": "123",
            "qty": 2,
            "unit": "EA",
            "nomenclature": "GPS Tray",
            "removed_part_no": "OLD-2",
            "installed_part_no": "NEW-2",
            "ata_chapter": "34",
        }
    ]


def test_normalize_logbook_payload_converts_blank_component_part_id_to_none():
    parsed = normalize_logbook_payload(
        {
            "componentParts": [
                {
                    "id": "",
                    "qty": 1,
                    "unit": "EA",
                    "nomenclature": "Ignition Harness",
                    "removedPartNo": "",
                    "installedPartNo": "NEW-3",
                }
            ]
        }
    )

    assert parsed["component_parts"] == [
        {
            "id": None,
            "qty": 1,
            "unit": "EA",
            "nomenclature": "Ignition Harness",
            "removed_part_no": None,
            "installed_part_no": "NEW-3",
        }
    ]
