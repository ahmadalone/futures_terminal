from setuptools import setup, find_packages
from pathlib import Path

def read_version():
    with open("VERSION", "r") as f:
        return f.read().strip()

def read_readme():
    return (Path(__file__).parent / "docs" / "README.md").read_text()

setup(
    name="futures-terminal",
    version=read_version(),
    author="FuturesTerminal Team",
    description="Professional multi-exchange futures trading terminal",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/futures-terminal",
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    include_package_data=True,
    install_requires=[
        "pydantic>=2.5.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "aiosqlite>=0.20.0",
        "ccxt>=4.2.0,<5.0",
        "numpy>=1.24.0",
        "pandas>=2.0",
        "PySide6>=6.5",
        "qasync>=0.27.0",
        "pyqtgraph>=0.13.0",
        "watchdog>=3.0.0",
        "torch>=2.0",
        "xgboost>=1.7",
        "lightgbm>=3.3",
        "scikit-learn>=1.2",
        "joblib>=1.2",
        "scipy>=1.10",
        "aiohttp>=3.8",
        "plyer>=2.0",
        "aiosmtplib>=1.1",
        "scikit-optimize>=0.9.0",
        "tqdm>=4.64",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "futures-terminal = main:main_launcher",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Trading Industry",
        "License :: MIT",
        "Programming Language :: Python :: 3.11",
    ],
)