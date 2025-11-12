from setuptools import setup

setup(
    name='databae',
    version="0.1.4.15",
    author='Mario Balibrera',
    author_email='mario.balibrera@gmail.com',
    license='MIT License',
    description='DATabase ABstraction lAyEr',
    long_description='sqlalchemy-based orm',
    packages=[
        'databae'
    ],
    zip_safe = False,
    install_requires = [
        "fyg >= 0.1.7.2",
        "requests >= 2.3.0",
        "sqlalchemy >= 2.0.30",
        "six >= 1.12.0"
    ],
    entry_points = '''''',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
