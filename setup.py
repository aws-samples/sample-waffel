from setuptools import setup, find_packages
from waffel import __version__

setup(
    name="waffel",
    version=__version__,
    description="Well-Architected Framework Friendly Enhanced Layout - Transform WAF reports into actionable insights",
    packages=find_packages(),
    install_requires=[
        "PyPDF2>=3.0.0",
        "openpyxl>=3.1.0",
        "InquirerPy>=0.3.4",
        "boto3>=1.26.0",
        "python-pptx>=0.6.21",
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "waffel=waffel.cli:main",
        ],
    },
    python_requires=">=3.7",
)
