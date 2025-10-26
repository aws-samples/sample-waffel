#!/usr/bin/env python3

from abc import ABC, abstractmethod

class DataSource(ABC):
    """Abstract base class for Well-Architected data sources"""
    
    @abstractmethod
    def get_workload_data(self):
        """Return standardized workload data structure
        
        Returns:
            dict: {
                'workload_properties': dict,
                'pillars': dict,  # {pillar_name: [questions]}
                'source_type': str,
                'source_info': str
            }
        """
        pass

def create_data_source(pdf_path=None, workload_id=None, lens_alias=None):
    """Factory function to create appropriate data source"""
    
    if pdf_path:
        from .data_source_pdf import PDFDataSource
        return PDFDataSource(pdf_path)
    else:
        from .data_source_api import APIDataSource
        return APIDataSource(workload_id, lens_alias)
