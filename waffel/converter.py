#!/usr/bin/env python3
"""Main converter class for transforming Well-Architected data to reports."""

from .excel_generator import ExcelGenerator
from .pptx_generator import PowerPointGenerator

def convert_to_excel(workload_data, output_path):
    """Convert Well-Architected data to Excel with all features"""

    source_type = workload_data.get('source_type', 'unknown')

    if source_type == 'pdf':
        print("📖 Converting PDF data to Excel...")
    elif source_type == 'api':
        print("🔄 Converting API data to Excel...")
    else:
        print("🔄 Converting data to Excel...")

    workload_props = workload_data['workload_properties']
    pillars = workload_data['pillars']

    workload_name = workload_props.get('Workload name', 'Unknown')
    total_questions = sum(len(questions) for questions in pillars.values())

    print(f"📋 Processing workload: {workload_name}")
    print(f"📊 Found {total_questions} questions across {len(pillars)} pillars")
    print("🎨 Creating Excel with all features...")

    # Generate Excel using dedicated generator
    excel_generator = ExcelGenerator()
    excel_generator.generate(pillars, workload_props, output_path)

    print(f"✅ Excel created: {output_path}")

    # Show workload properties
    print("\n📋 WORKLOAD PROPERTIES:")
    for prop, value in workload_props.items():
        if value:
            display_value = str(value)[:60] + "..." if len(str(value)) > 60 else str(value)
            print(f"   {prop}: {display_value}")

def convert_to_powerpoint(workload_data, output_path):
    """Convert Well-Architected data to PowerPoint presentation"""

    source_type = workload_data.get('source_type', 'unknown')

    if source_type == 'pdf':
        print("📖 Converting PDF data to PowerPoint...")
    elif source_type == 'api':
        print("🔄 Converting API data to PowerPoint...")
    else:
        print("🔄 Converting data to PowerPoint...")

    workload_props = workload_data['workload_properties']
    pillars = workload_data['pillars']

    workload_name = workload_props.get('Workload name', 'Unknown')
    total_items = sum(len(q.get('improvement_items', [])) for questions in pillars.values() for q in questions)

    print(f"📋 Processing workload: {workload_name}")
    print(f"📊 Found {total_items} improvement items across {len(pillars)} pillars")
    print("🎨 Creating PowerPoint presentation...")

    # Generate PowerPoint using dedicated generator
    pptx_generator = PowerPointGenerator()
    pptx_generator.generate(pillars, workload_props, output_path)

    print(f"✅ PowerPoint created: {output_path}")

    # Show summary
    print("\n📋 IMPROVEMENT ITEMS BY PILLAR:")
    for pillar_name, questions in pillars.items():
        pillar_items = sum(len(q.get('improvement_items', [])) for q in questions)
        if pillar_items > 0:
            print(f"   {pillar_name}: {pillar_items} items")
