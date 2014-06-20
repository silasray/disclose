from setuptools import setup, find_packages

setup(name='disclose',
      version='0.2.3',
      author='Silas Ray',
      author_email='silas.ray@nytimes.com',
      url='https://github.com/silasray/disclose',
      license='Apache2.0',
      description='A utility for test verifications',
      long_description='A utility that facilitates automatic logging of verification steps.',
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Information Technology',
                   'Topic :: Software Development :: Quality Assurance',
                   'Topic :: Software Development :: Testing'],
      packages=find_packages())