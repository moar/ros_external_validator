from setuptools import setup, find_packages
from catkin_pkg.python_setup import generate_distutils_setup

setup_args = generate_distutils_setup(
    name='ulises_test_utils',
    version='1.0.0',
    package_dir={"": "src"},
    packages= find_packages(where="src"),
    url='',
    license='GPLv3',
    author='Gorka Olalde',
    author_email='golalde@mondragon.edu',
    maintainer='Gorka Olalde',
    maintainer_email='golalde@mondragon.edu',
    description='ULISES test integration tools',
    install_requires=['paho-mqtt']
)
setup(**setup_args)
