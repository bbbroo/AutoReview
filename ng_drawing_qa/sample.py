from __future__ import annotations

from pathlib import Path
import csv
import fitz


def generate_sample_project(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "sample_natural_gas_drawing_set.pdf"

    doc = fitz.open()
    pages = [
        ("G-001", "Cover Sheet", "ASME B31.8. DESIGN PRESSURE 720 PSIG. IFC."),
        ("G-002", "Drawing Index", "G-001 COVER\nG-002 INDEX\nP-201 P&ID\nM-101 PIPING PLAN\nM-501 DETAILS"),
        ("P-201", "Regulator Station P&ID", '6"-G-101 BV-101 REG-101 REG-102 PSV-101 PT-101 PI-101 RELIEF VENT STACK MAOP 720 PSIG SEE 4/M-501'),
        ("M-101", "Piping Plan", '6"-G-101 BV-101 BV-999 TIE-IN TI-001 EXISTING GAS MAIN. ASME B31.3. DESIGN PRESSURE 740 PSIG.'),
        ("M-501", "Piping Details", "DETAIL 4 RELIEF VENT TERMINATION. TEST PRESSURE 1080 PSIG. FBE COATING. API 5L X52."),
    ]
    for sheet, title, body in pages:
        page = doc.new_page(width=792, height=612)
        page.insert_text((42, 50), f"{sheet} - {title}", fontsize=18)
        page.insert_text((42, 110), body, fontsize=12)
        # Rough title block lower-right.
        page.draw_rect(fitz.Rect(520, 470, 770, 590))
        page.insert_text((530, 492), f"SHEET NUMBER: {sheet}", fontsize=10)
        page.insert_text((530, 512), f"TITLE: {title}", fontsize=10)
        page.insert_text((530, 532), "REV: 0", fontsize=10)
        page.insert_text((600, 532), "DATE: 2026-06-14", fontsize=10)
        page.insert_text((530, 552), "STATUS: IFC", fontsize=10)
        page.insert_text((600, 552), "CHK: JD", fontsize=10)

    doc.save(pdf_path)
    doc.close()

    def write_csv(name, headers, rows):
        with (out_dir / name).open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)

    write_csv("drawing_index.csv", ["sheet_number", "sheet_title", "revision", "issue_date", "status"], [
        ["G-001", "Cover Sheet", "0", "2026-06-14", "IFC"],
        ["G-002", "Drawing Index", "0", "2026-06-14", "IFC"],
        ["P-201", "Regulator Station P&ID", "0", "2026-06-14", "IFC"],
        ["M-101", "Piping Plan", "0", "2026-06-14", "IFC"],
        ["M-501", "Piping Details", "0", "2026-06-14", "IFC"],
        ["E-101", "Electrical Plan", "0", "2026-06-14", "IFC"],
    ])
    write_csv("valve_list.csv", ["tag", "type", "size", "service"], [
        ["BV-101", "Ball Valve", "6 in", "Inlet"],
        ["PSV-101", "Relief Valve", "2 in", "Relief"],
        ["REG-101", "Regulator", "4 in", "Worker"],
        ["REG-102", "Regulator", "4 in", "Monitor"],
        ["BV-102", "Ball Valve", "6 in", "Outlet"],
    ])
    write_csv("line_list.csv", ["line_number", "size", "service", "maop_psig", "test_pressure_psig"], [
        ["6-G-101", "6 in", "Gas", "720", "1080"],
        ["4-G-102", "4 in", "Gas", "125", "188"],
    ])
    write_csv("instrument_index.csv", ["tag", "type", "service"], [
        ["PT-101", "Pressure Transmitter", "Downstream"],
        ["PI-101", "Pressure Indicator", "Upstream"],
        ["PSH-101", "Pressure Switch High", "Overpressure"],
    ])
    write_csv("equipment_list.csv", ["tag", "type", "service"], [
        ["REG-101", "Regulator", "Worker"],
        ["REG-102", "Regulator", "Monitor"],
    ])
