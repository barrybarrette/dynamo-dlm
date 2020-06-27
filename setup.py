from setuptools import setup, find_packages

with open('README.md', 'r') as readme_file:
    long_description = readme_file.read()

setup(
    name='dynamo-dlm',
    version='1.0.0',
    author='Barry Barrette',
    author_email='barrybarrette@gmail.com',
    description='Distributed lock manager for Python using AWS DynamoDB for persistence',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/whitebarry/dynamo-dlm',
    packages=find_packages()
)
