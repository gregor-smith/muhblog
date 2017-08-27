import setuptools

setuptools.setup(
    name='muhblog',
    version='0.1',
    license='MIT',
    author='Gregor Smith',
    author_email='gregor_smith@outlook.com',
    url='https://github.com/gregor-smith/muhblog',
    packages=['muhblog'],
    include_package_data=True,
    platforms='any',
    install_requires=['click', 'Flask', 'python-slugify', 'peewee',
                      'mistune', 'Frozen-Flask', 'pyScss'],
    classifiers=['Development Status :: 3 - Alpha',
                 'Framework :: Flask',
                 'License :: OSI Approved :: MIT License',
                 'Programming Language :: Python :: 3.6'],
    zip_safe=False
)
