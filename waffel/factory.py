#!/usr/bin/env python3
"""Factory for creating data sources."""

from .data_source_pdf import PDFDataSource
from .data_source_api import APIDataSource

def create_data_source(pdf_path=None, workload_id=None, lens_alias=None):
    """Factory function to create appropriate data source"""
    if pdf_path:
        return PDFDataSource(pdf_path)
    return APIDataSource(workload_id, lens_alias)
