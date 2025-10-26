from setuptools import setup, find_packages

setup(
    name="waffel",
    version="1.0.0",
    description="Well-Architected Framework Friendly Enhanced Layout - Transform WAF reports into actionable insights",
    packages=find_packages(),
    install_requires=[
        "PyPDF2>=3.0.0",
        "openpyxl>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "waffel=waffel.cli:main",
        ],
    },
    python_requires=">=3.7",
)
