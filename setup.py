from setuptools import setup, find_packages

setup(
    name='common_stock_classes',
    version='0.1.0',
    author='Andrew Kravchuk',
    author_email='andrewkravchuk97@gmail.com',
    packages=find_packages(where="src"),
    package_dir={"": "src"}, 
    description='',
    python_requires='>=3.10',
)

