from setuptools import find_packages, setup

setup(
    name="src",
    packages=find_packages(),
    version="0.1.0",
    description="the analysis part",
    author="sboomi",
    license="MIT",
    install_requires=[
        "Click",
    ],
    entry_points="""
        [console_scripts]
        scitrend-analysis=src.__main__:main
    """,
)
