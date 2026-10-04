#!/usr/bin/env python3
"""Setup configuration for MarketSentinel."""

from pathlib import Path
from setuptools import find_packages, setup

readme_path = Path("README.md")
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "MarketSentinel"

setup(
    name="marketsentinel",
    version="1.0.0",
    description="Enterprise Market Intelligence, Automated Reporting, and Scheduling Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Jateen Jadhav",
    author_email="jatinxwolverine@users.noreply.github.com",
    url="https://github.com/jatinxwolverine/marketsentinel",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "pyyaml>=6.0.0",
        "reportlab>=4.0.0",
        "matplotlib>=3.8.0",
        "apscheduler>=3.10.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0.0"],
    },
    entry_points={
        "console_scripts": [
            "marketsentinel=marketsentinel.cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.13",
        "Topic :: System :: Monitoring",
    ],
)
