#!/usr/bin/env python3
import argparse
import os
import sys
from InquirerPy import inquirer
from .converter import convert_to_excel, convert_to_powerpoint
from .data_source import create_data_source
from .data_source_api import APIDataSource

def get_available_sources():
    """Get all available sources: PDFs and WA workloads"""
    sources = []

    # Get PDF files
    pdf_files = [f for f in os.listdir('.') if f.lower().endswith('.pdf')]
    for pdf in pdf_files:
        sources.append({
            'type': 'pdf',
            'display': f"📄 {pdf}",
            'value': pdf
        })

    # Try to get WA workloads
    try:
        api = APIDataSource()
        workloads = api.get_workloads()
        for w in workloads:
            description = w.get('Description', 'No description')
            if len(description) > 40:
                description = description[:37] + "..."
            sources.append({
                'type': 'api',
                'display': f"⌬ {w['WorkloadName']} - {description}",
                'value': w['WorkloadId']
            })
    except Exception:
        # Silently ignore AWS access issues
        pass

    return sources

def select_source():
    """Select source from combined PDF and workload list"""
    sources = get_available_sources()

    if not sources:
        print("No PDF files found in current directory and no AWS Well-Architected workloads accessible.")
        print("Please ensure you have:")
        print("  • PDF files in the current directory, OR")
        print("  • AWS credentials configured with Well-Architected access")
        sys.exit(1)

    if len(sources) == 1:
        source = sources[0]
        print(f"Found single source: {source['display']}")
        return source

    choices = [s['display'] for s in sources]

    selection = inquirer.select(
        message="Select a source:",
        choices=choices
    ).execute()

    # Find the selected source
    return next(s for s in sources if s['display'] == selection)

def main():
    parser = argparse.ArgumentParser(description="Convert AWS Well-Architected Framework data to Excel or PowerPoint")
    parser.add_argument("input_file", nargs="?", help="Path to PDF file (optional)")
    parser.add_argument("-o", "--output", help="Output Excel file path")
    parser.add_argument("-w", "--workload-id", help="Well-Architected workload ID")
    parser.add_argument("-l", "--lens-alias", help="Well-Architected lens alias")
    parser.add_argument("--api", action="store_true", help="Force API mode (ignore PDF files)")
    parser.add_argument("--pptx", action="store_true", help="Generate PowerPoint presentation instead of Excel")

    args = parser.parse_args()

    # Determine input source
    pdf_file = None
    workload_id = args.workload_id
    lens_alias = args.lens_alias

    if args.input_file:
        # Direct PDF file specified
        pdf_file = args.input_file
        if not os.path.exists(pdf_file):
            print(f"Error: File '{pdf_file}' not found")
            sys.exit(1)
    elif args.api or workload_id or lens_alias:
        # API mode explicitly requested or parameters provided
        pdf_file = None
    else:
        # No parameters - show combined selection
        source = select_source()
        if source['type'] == 'pdf':
            pdf_file = source['value']
        else:
            workload_id = source['value']

    try:
        # Create data source
        data_source = create_data_source(pdf_file, workload_id, lens_alias)

        # Get workload data
        workload_data = data_source.get_workload_data()

        # Generate output path
        output_file = args.output
        if not output_file:
            if pdf_file:
                base_name = os.path.splitext(os.path.basename(pdf_file))[0]
            else:
                workload_name = workload_data['workload_properties'].get('Workload name', 'workload')
                base_name = workload_name.replace(' ', '_')

            if args.pptx:
                output_file = f"{base_name}_WA_Presentation.pptx"
            else:
                output_file = f"{base_name}_WA_Assessment.xlsx"

        # Convert to output format
        if args.pptx:
            convert_to_powerpoint(workload_data, output_file)
        else:
            convert_to_excel(workload_data, output_file)

        source_info = pdf_file if pdf_file else f"API (Workload: {workload_data.get('workload_id', 'N/A')})"
        print(f"Successfully converted '{source_info}' to '{output_file}'")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
