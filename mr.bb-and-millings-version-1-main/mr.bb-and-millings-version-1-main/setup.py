from setuptools import setup, find_packages

setup(
    name="festival-logistics",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Flask>=2.0.0",
        "Flask-Login>=0.5.0",
        "Flask-WTF>=1.0.0",
        "Flask-Limiter>=2.8.0",
        "Werkzeug>=2.0.0",
        "openpyxl>=3.0.0",
        "python-dotenv>=0.19.0",
    ],
    python_requires=">=3.8",
)
