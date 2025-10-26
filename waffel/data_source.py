#!/usr/bin/env python3
"""Abstract base class for data sources."""

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
        raise NotImplementedError("Subclasses must implement extract_data method")
